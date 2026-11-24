import io, os, hmac, ipaddress, socket, time
from urllib.parse import urlparse
import httpx
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageOps
from rembg import new_session, remove

MODEL = os.environ.get("BG_MODEL", "u2netp")  # Apache-2.0 (U-2-Net), run through rembg (MIT)
MAX_BYTES = int(os.environ.get("MAX_BYTES", 10 * 1024 * 1024))
MAX_SIDE = int(os.environ.get("MAX_SIDE", 4096))
WORK_SIDE = int(os.environ.get("WORK_SIDE", 1024))  # larger inputs are processed at this size, mask scaled back
SECRETS = {k: v for k, v in (("rapidapi", os.environ.get("PROXY_SECRET", "")),
                             ("apimarket", os.environ.get("PROXY_SECRET_APIMARKET", "")),
                             ("zyla", os.environ.get("PROXY_SECRET_ZYLA", ""))) if v}
session = new_session(MODEL)
app = FastAPI(title="Background Removal API", docs_url=None, redoc_url=None, openapi_url=None)


def err(msg, status):
    return JSONResponse({"error": msg}, status_code=status)


def authed(req: Request):
    h = req.headers.get("x-rapidapi-proxy-secret", "")
    return any(hmac.compare_digest(h, s) for s in SECRETS.values()) if h else False


def public_host(url):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    try:
        for ai in socket.getaddrinfo(u.hostname, None):
            ip = ipaddress.ip_address(ai[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
    except Exception:
        return False
    return True


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL}


@app.post("/remove")
async def remove_bg(req: Request, image: UploadFile = File(None), image_url: str = Form(None),
                    bgcolor: str = Form(None), crop: bool = Form(False)):
    if not authed(req):
        return err("forbidden", 403)
    t0 = time.time()
    if image is not None:
        data = await image.read(MAX_BYTES + 1)
    else:
        if image_url is None:
            try:
                image_url = (await req.json()).get("image_url")
            except Exception:
                image_url = None
        if not image_url:
            return err("send multipart field 'image' (file) or 'image_url'", 400)
        if not public_host(image_url):
            return err("image_url must be a public http(s) URL", 400)
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as c:
                async with c.stream("GET", image_url) as r:
                    if r.status_code != 200:
                        return err(f"image_url returned HTTP {r.status_code}", 400)
                    data = b""
                    async for ch in r.aiter_bytes():
                        data += ch
                        if len(data) > MAX_BYTES:
                            break
        except Exception as e:
            return err(f"could not fetch image_url: {type(e).__name__}", 400)
    if not data:
        return err("empty image", 400)
    if len(data) > MAX_BYTES:
        return err(f"image larger than {MAX_BYTES // 1048576} MB", 413)
    try:
        im = Image.open(io.BytesIO(data))
        w, h = im.size
        if max(w, h) > MAX_SIDE:
            return err(f"image larger than {MAX_SIDE}px on a side", 413)
        im = ImageOps.exif_transpose(im).convert("RGBA")
    except Exception:
        return err("not a valid image (PNG, JPEG, WebP, BMP, GIF)", 400)
    work = im
    if max(w, h) > WORK_SIDE:
        s = WORK_SIDE / max(w, h)
        work = im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    mask = remove(work.convert("RGB"), session=session, only_mask=True)
    if mask.size != im.size:
        mask = mask.resize(im.size, Image.LANCZOS)
    out = im.copy()
    out.putalpha(mask)
    if bgcolor:
        c = bgcolor.lstrip("#")
        if len(c) != 6 or any(x not in "0123456789abcdefABCDEF" for x in c):
            return err("bgcolor must be 6 hex digits", 400)
        bg = Image.new("RGBA", out.size, "#" + c)
        out = Image.alpha_composite(bg, out)
    if crop:
        box = mask.point(lambda p: 255 if p > 8 else 0).getbbox()
        if box:
            out = out.crop(box)
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png",
                    headers={"x-processing-ms": str(int((time.time() - t0) * 1000)), "x-model": MODEL})
