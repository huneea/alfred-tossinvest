"""토스증권 Open API 를 Alfred 워크플로우에서 쓰기 위한 최소 클라이언트.

의존성은 파이썬 표준 라이브러리뿐이다. Alfred 는 스크립트를 최소 PATH
(/bin:/usr/bin:/usr/local/bin)로 실행하므로 pyenv·nvm 같은 버전 매니저가 잡히지
않는다. 그래서 시스템 /usr/bin/python3 (3.9) 에서 그대로 도는 코드만 쓴다.
"""

__all__ = ["alfred", "auth", "client", "config", "errors"]
