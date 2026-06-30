# 설치형 WordPress 자격증명(Application Password)이 올바른지 점검한다
import requests
from requests.auth import HTTPBasicAuth

from .config import env


def main():
    url = env("WP_SITE_URL", "").rstrip("/")
    if not url:
        print("WP_SITE_URL 이 비어 있습니다. .env 를 확인하세요. (SETUP.md 6단계)")
        return
    r = requests.get(
        f"{url}/wp-json/wp/v2/users/me",
        auth=HTTPBasicAuth(env("WP_USERNAME"), env("WP_APP_PASSWORD").replace(" ", "")),
        timeout=20,
    )
    if r.status_code >= 400:
        print(f"인증 실패 {r.status_code}: {r.text}")
        print("힌트. https 인지, Application Password 가 맞는지, REST API 가 열려 있는지 확인하세요.")
        return
    me = r.json()
    print(f"인증 성공. 로그인 사용자: {me.get('name')} (id {me.get('id')})")


if __name__ == "__main__":
    main()
