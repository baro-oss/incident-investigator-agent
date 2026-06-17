# auth-service

Xác thực JWT token và phân quyền. Mọi request nội bộ đi qua đây để verify token.
Leaf node — không gọi service khác, nhưng được payment-gateway gọi để xác thực.

- `v1.1.0` (GOOD): `jwt.decode(..., leeway=30)` + try/except `AuthenticationError`.
- `v1.2.0` (BAD): bỏ `leeway` + bỏ try/except + bump PyJWT 2.7→2.8 → token hợp lệ
  bị reject khi đồng hồ lệch → HTTP_401 hàng loạt.

> Repo demo — source đọc qua GitLab code MCP (READ-ONLY).
