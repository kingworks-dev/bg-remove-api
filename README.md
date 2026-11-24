# Background Removal API

FastAPI service: `POST /remove` (multipart `image` or form `image_url`) returns a PNG with an alpha channel; `GET /health`.
Model: U-2-Net-p (u2netp, Apache-2.0, https://github.com/xuebinqin/U-2-Net). Limits: 10 MB, 4096 px per side.
Requests need the marketplace proxy secret header (`X-RapidAPI-Proxy-Secret`), set as environment variable `PROXY_SECRET`.
Hosted, paid version: see the RapidAPI listing "Background Removal API". License of this code: MIT.
