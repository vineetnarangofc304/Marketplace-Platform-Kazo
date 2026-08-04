# Auth Testing Playbook

Focused checklist for the login bug verification:

1. Verify seeded admin users in MongoDB using the configured `MONGO_URL` and `DB_NAME`.
2. Verify `POST /api/auth/login` succeeds for both `admin@fundle.ai / admin123` and `admin@kazo.com / admin123` and returns an access token plus user object.
3. Verify authenticated follow-up (`GET /api/auth/me`) succeeds using the returned cookie/token.
4. Verify the frontend login form is prefilled with `admin@fundle.ai`, shows matching demo credentials, and redirects away from `/login` after clicking Sign in.
5. Restart backend in preview, then verify both admin users still exist and can log in.