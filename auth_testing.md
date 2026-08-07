# AssetFlow Campus Auth Testing Checklist

1. Create a test user and session in the configured MongoDB database using a custom `user_id` and a 7-day `session_token`.
2. Verify `GET /api/auth/me` with the session token in the Authorization header.
3. Verify protected AssetFlow endpoints with the same session token.
4. In a browser, set the session cookie and confirm the dashboard loads without redirecting to login.
5. Verify OAuth callback detection reads `useLocation().hash`, exchanges `session_id` server-side, and redirects to the dashboard.
6. Confirm all MongoDB responses exclude `_id`, session expiry is timezone-safe, and logout clears the session.