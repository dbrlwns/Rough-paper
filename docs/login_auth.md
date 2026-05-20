## Authentication

```python
@sensitive_variables("credentials")
def authenticate(request=None, **credentials):
    """
    If the given credentials are valid, return a User object.
    """
    for backend, backend_path in _get_compatible_backends(request, **credentials):
        try:
            user = backend.authenticate(request, **credentials)
        except PermissionDenied:
            # This backend says to stop in our tracks - this user should not be
            # allowed in at all.
            break
        if user is None:
            continue
        # Annotate the user object with the path of the backend.
        user.backend = backend_path
        return user

    # The credentials supplied are invalid to all backends, fire signal
    user_login_failed.send(
        sender=__name__, credentials=_clean_credentials(credentials), request=request
    )
```

backend 변수는 인증 처리를 하는 로직 모듈,
서버 내의 id/pw나 email 연동 Oauth 로그인 등의 방식이 등록 가능하고,
for backend, backend_path in ...  는 등록된 인증 방식들을 하나씩 시도한다.

backend를 시도하며 인증 성공 시, User 객체를 반환한다.
이때, user.backend에 backend_path 저장은 어떤 인증방식을 사용했는지를 저장함.

위의 함수는 전역 authenticate() 함수고, 각 backend의 authenticate()를 추가로 호출하게 된다.(인터페이스 역할)
ex) ModelBackend(BaseBackend), EmailBackend(BaseBackend) 등의 클래스 내에 실제 구현체 존재

```python
for backend_path in settings.AUTHENTICATION_BACKENDS:
```
전역 authenticate() 함수의 반복문을 추적해가면 위와 같은 내용을 반환하고, 
```python
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
```
이러한 내용을 확인할 수 있다. 

만약 Email 인증을 추가하면 AUTHENTICATION_BACKENDS에 ...EmailBackend를 추가해주면
전역 함수인 authenticate()는 그대로지만 내부적으로는 EmailBackend.authenticate()가 호출된다.

즉, 외부 접근(인증 절차)은 그대로 유지하면서, 내부 인증 절차만 추가가 쉽게 가능하다

 
```python
def login(request, user, backend=None):
    """
    Persist a user id and a backend in the request. This way a user doesn't
    have to reauthenticate on every request. Note that data set during
    the anonymous session is retained when the user logs in.
    """
    # RemovedInDjango61Warning: When the deprecation ends, replace with:
    # session_auth_hash = user.get_session_auth_hash()
    session_auth_hash = ""
    # RemovedInDjango61Warning.
    if user is None:
        user = request.user
        warnings.warn(
            "Fallback to request.user when user is None will be removed.",
            RemovedInDjango61Warning,
            stacklevel=2,
        )

    # RemovedInDjango61Warning.
    if hasattr(user, "get_session_auth_hash"):
        session_auth_hash = user.get_session_auth_hash()

    if SESSION_KEY in request.session:
        if _get_user_session_key(request) != user.pk or (
            session_auth_hash
            and not constant_time_compare(
                request.session.get(HASH_SESSION_KEY, ""), session_auth_hash
            )
        ):
            # To avoid reusing another user's session, create a new, empty
            # session if the existing session corresponds to a different
            # authenticated user.
            request.session.flush()
    else:
        request.session.cycle_key()

    backend = _get_backend_from_user(user=user, backend=backend)

    request.session[SESSION_KEY] = user._meta.pk.value_to_string(user)
    request.session[BACKEND_SESSION_KEY] = backend
    request.session[HASH_SESSION_KEY] = session_auth_hash
    if hasattr(request, "user"):
        request.user = user
    rotate_token(request)
    user_logged_in.send(sender=user.__class__, request=request, user=user)
```

RemovedInDjango61Warning : Django 6.1부터는 없어질 수 있다는 버전 호환성 처리 코드
login() 요청에 user 객체(user==None)없이 호출가능한 부분이 Django 6.1 이후에는 제거될 예정

if hasattr(user, "get_session_auth_hash"): 는 user 객체가 get_session_auth_hash 메서드를 갖고 있는지 확인과 동시에 user 객체가 세션 인증 해시를 제공할 수 있는지 확인하는 역할을 수행함.
-> 사용자가 비밀번호 변경 등을 하고난 뒤에, 기존 세션 유지 시 변경이 안될 수 있으므로 Django는 세션에 저장된 auth hash와 현재 user의 auth hash를 비교해서 다르면 세션을 무효화 한다.

```python
def get_session_auth_hash(self):
    """
    Return an HMAC of the password field.
    """
    return self._get_session_auth_hash()


def _get_session_auth_hash(self, secret=None):
    key_salt = "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash"
    return salted_hmac(
        key_salt,
        self.password, # DB에 해시화되어 저장된 데이터임.
        secret=secret,
        algorithm="sha256",
    ).hexdigest()
```
외부에서 사용하는 인터페이스와 내부에서 실제 hash 인증값을 계산하는 내부 함수가 AbstractBaseUser에 있음.
내부 함수에는 secret 파라미터를 추가로 받는데, 해시 만들 때 사용하는 비밀키를 말한다. settings.py에서 변경

HMAC (Hash-based Message Authentication Code) : 비밀키를 사용한 인증용 해시 값

다음에 세션에 로그인 정보가 있는지 확인하고, 있을 시에 기존 세션 사용자와 현재 사용자가 같은지 확인하고, 
auth_hash가 다르거나 사용자가 틀리면 세션 정보와 키를 삭제하고(flush), 
기존 로그인 정보가 없는 상태면 세션 데이터 유지 후 세션 키만 새로 발급(cycle_key) 한다.
(세션 고정 공격을 방지)

_get_user_session_key(request) != user.pk는 세션에 저장된 사용자와 지금 로그인하려는 사용자를 구분

backend와 세션 정보를 요청에 담고 현재 요청 객체의 user도 로그인된 사용자 정보로 넘김. 이렇게 사용하면 login() 호출 이후의 view에서 request.user로 사용할 수 있음.

rotate_token(request) : 로그인 전과 후의 사용자 보안 상태가 변경되므로 CSRF 토큰 갱신

user_logged_in.send(sender=user.__class__, request=request, user=user)
: 사용자가 로그인했다는 Django signal을 보냄. Signal 클래스는 이벤트 알림 시스템.  Signal.send() 함수는 연결되어 있는 receiver 함수를 실행한다. receiver 함수가 없으면 아무 동작도 하지 않음.

나중에 로그인 기록 저장이나 통계, 추가 보안 처리 시 receiver 함수를 연결해 사용할 수 있음.
login() 함수 내에 작성도 가능하지만 login() 함수는 그대로 두고 부가 기능만 따로 붙이기 위해 이렇게 사용함.


```python
def logout(request):
    """
    Remove the authenticated user's ID from the request and flush their session
    data.
    """
    # Dispatch the signal before the user is logged out so the receivers have a
    # chance to find out *who* logged out.
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", True):
        user = None
    user_logged_out.send(sender=user.__class__, request=request, user=user)
    request.session.flush()
    if hasattr(request, "user"):
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
```

요청 객체의 사용자를 가져와 user가 인증되지 않은 상태면 None으로 바꾼다.
user_logged_out로 signal 보낼 때, 실제 user가 없기 때문에 user 변수를 None으로 바꿈 + 세션 지우기 전에 전송
이후 세션 초기화하고 request.user를 AnonymousUser로 교체



## request.user 반환
```python
# middleware.py
class AuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not hasattr(request, "session"):
            raise ImproperlyConfigured(
                "The Django authentication middleware requires session "
                "middleware to be installed. Edit your MIDDLEWARE setting to "
                "insert "
                "'django.contrib.sessions.middleware.SessionMiddleware' before "
                "'django.contrib.auth.middleware.AuthenticationMiddleware'."
            )
        request.user = SimpleLazyObject(lambda: get_user(request))
        request.auser = partial(auser, request)
```
LazyObject에 대한 이해
진짜 객체를 바로 만들지 않고 필요할 때 까지 미루는 객체
요청이 들어올 때마다 get_user(request)를 실행하지 않고 나중에 request.user가 실제로 사용될 때 실행하게 함.
지연 로딩으로 Django의 성능을 보장하기 위해 사용함.

요청이 들어오면 AuthenticationMiddleware를 실행하고, request.user에 Lazy 객체가 들어간다.
실제로 request.user 값을 사용할 때 get_user(request)를 실행하고 

user_id = _get_user_session_key(request)
backend_path = request.session[BACKEND_SESSION_KEY]                          
session_hash = request.session.get(HASH_SESSION_KEY)
세션에서 위 3개의 값을 읽고 정상 User 객체 또는 AnonymousUser 객체를 반환한다.
