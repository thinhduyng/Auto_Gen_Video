# Video Factory

**Một kịch bản → 6 engine dựng 6 phiên bản video dọc 9:16 → xem song song trên web → chọn 1 bản để đăng TikTok / YouTube Shorts.**

Chạy trên Linux và Windows bằng các script Python, giọng đọc tiếng Việt miễn phí (Edge TTS), phụ đề karaoke khớp từng chữ. Ảnh minh hoạ đổi theo từng câu,
lấy từ Pixabay / Pexels (ảnh chụp, miễn phí), **tự vẽ bằng card đồ hoạ của máy** (ComfyUI + SDXL-Lightning),
hoặc ảnh thật trên Wikimedia Commons cho video về người và sự kiện có thật. Gemini (miễn phí) viết nháp kịch bản từ một chủ đề.

![Cùng một kịch bản qua 6 engine](docs/so-sanh-01-10/0-cau-treo-6-engine.jpg)

| Engine | Phong cách | Thời gian render (video 1–2 phút, đo trên máy dựng hệ thống) |
|---|---|---|
| [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | Clip stock (hoặc ảnh tự vẽ) + phụ đề; tuỳ chọn **bản podcast** giọng ElevenLabs | ~8 phút (3–27) |
| Stock khớp lời (viết riêng) | Clip Pixabay / Pexels đổi theo **từng câu**, chữ và số hiện đúng lúc đọc | ~2,5 phút |
| [AI-auto-generate-video](https://github.com/huytranvan2010/AI-auto-generate-video) | Template poster động trên ảnh đổi theo câu | ~3 phút |
| [HyperFrames](https://www.npmjs.com/package/hyperframes) | Học thuật nền sáng: sơ đồ dựng dần, phụ đề karaoke | ~4 phút |
| [Pixelle-Video](https://github.com/ATH-MaaS/Pixelle-Video) | Mỗi câu một khung: ảnh + chữ | ~2 phút |
| [Remotion](https://www.remotion.dev) | Nền tối, phụ đề kiểu TikTok | ~7 phút |

Hệ thống **không tự đăng** video: bạn xem, chọn bản ưng ý, rồi tự tải lên kênh.

## Chạy trên Linux

Cần Python **≥ 3.11**, Git, `uv`, Node.js **≥ 22** (kèm npm), FFmpeg/ffprobe và Chrome hoặc Chromium.
Trên Debian/Ubuntu, cài công cụ nền: `sudo apt install python3 git ffmpeg`. Cài
[uv](https://docs.astral.sh/uv/getting-started/installation/), [Node.js](https://nodejs.org/en/download)
và Chrome/Chromium nếu máy chưa có. Installer chỉ kiểm tra các phần mềm hệ thống; không tự chạy sudo.

Từ thư mục repo, cấu hình nhẹ phù hợp máy chỉ có GPU tích hợp:

```bash
uv run --no-project --python 3.12 python cai-dat.py --engines hyperframes remotion broll
# Mở .env bằng editor và điền GEMINI_API_KEY và PIXABAY_API_KEY (hoặc PEXELS_API_KEY).
source .venv/bin/activate
python chay-web.py
```

Web chạy ở **http://127.0.0.1:8600**, tự mở trình duyệt sau khi server sẵn sàng. **Ctrl+C** dừng server.
Qua SSH hoặc không muốn mở trình duyệt: `python chay-web.py --no-browser` (sau khi kích hoạt `.venv`). Đổi cổng: `--port 8601` hoặc
`FACTORY_PORT=8601` trong `.env`. Chrome/Chromium được tìm trong `PATH`; có thể chỉ định `CHROME_PATH=/usr/bin/chromium`.

Không cần GPU để dựng video hoặc dùng VieNeu trên CPU. Có thể đặt `FACTORY_PARALLEL=1` trong `.env` để giảm số render
đồng thời. Thiếu key Pixabay/Pexels thì engine stock báo chưa sẵn sàng; video slide có `"images": false` không cần stock.
Viết nháp tự động vẫn cần key Gemini. VieNeu chạy trong một server riêng: xem hướng dẫn giọng VieNeu bên dưới.

Các lệnh Python (sau khi kích hoạt `.venv`):

| Lệnh | Công dụng |
|---|---|
| `python cai-dat.py` | Cài cả 6 engine; giữ nguyên checkout đã có, không xoá thay đổi của bạn |
| `python cai-dat.py --check --engines hyperframes remotion` | Chỉ kiểm tra phần mềm và tình trạng; không cài hoặc tạo `.env` |
| `python vf-python.py -m factory.status` | Chạy Python trong `.venv` từ thư mục gốc repo |
| `python vf-python.py -m factory.try_engine hyperframes content/demo/flow-demo.json` | Thử một engine |
| `python cai-comfyui.py --device cpu` | Cài ComfyUI riêng và model SDXL (~7 GB), tuỳ chọn |
| `python chay-comfyui.py` | Bật ComfyUI bằng thiết bị đã chọn lúc cài |

Installer mặc định dùng Python 3.12 do uv quản lý. Nếu muốn dùng Python đã cài, thêm `--python /usr/bin/python3`
(các engine bên ngoài có thể cần đúng phiên bản của chúng). Có thể chọn engine bằng `--engines`;
factory có sẵn **faster-whisper 1.2.1** và **PyAV < 19** cho căn phụ đề VieNeu. Các phụ thuộc này được khai báo
trong `pyproject.toml` và ghim trong `uv.lock`; `uv sync --locked` giữ chúng trong `.venv`. Flag `--with-whisper`
được chấp nhận để tương thích với các lệnh cài đặt cũ, không cần cho cài đặt thông thường.

Sau khi cài, kích hoạt `.venv` trong mỗi terminal Linux bằng `source .venv/bin/activate`; từ đó dùng `python`
thay cho `python3` trong các lệnh của repo. `python` trỏ tới interpreter của dự án. Có thể chạy không cần kích hoạt
bằng `uv run --locked python chay-web.py`. Khi cập nhật các phụ thuộc đã ghim, chạy `uv sync --locked` từ thư mục gốc.
Các môi trường engine bên ngoài, bao gồm VieNeu, được quản lý riêng.

Pixelle cần Chromium riêng của Playwright; installer tải trình duyệt này. Nếu thiếu thư viện hệ thống của trình duyệt,
chạy `engines/pixelle-video/.venv/bin/python -m playwright install-deps chromium` theo hướng dẫn Playwright (có thể cần sudo).
Các repo engine được ghim theo commit trong `setup/install.py`; môi trường Python và Node của mỗi engine tách riêng.
Cache uv/npm và Python uv tải nằm trong `.cache/`.

## Mục lục

1. [Cần chuẩn bị gì](#1-cần-chuẩn-bị-gì)
2. [Đăng ký tài khoản và lấy key](#2-đăng-ký-tài-khoản-và-lấy-key)
3. [Cài phần mềm nền](#3-cài-phần-mềm-nền)
4. [Tải mã và cài đặt](#4-tải-mã-và-cài-đặt)
5. [Điền key](#5-điền-key)
6. [Chạy web](#6-chạy-web)
7. [Làm video — cách bình thường](#7-làm-video--cách-bình-thường)
8. [Tự tạo ảnh bằng AI trên máy](#8-tự-tạo-ảnh-bằng-ai-trên-máy)
9. [Ảnh thật cho người và sự kiện có thật](#9-ảnh-thật-cho-người-và-sự-kiện-có-thật)
10. [Bản podcast giọng ElevenLabs](#10-bản-podcast-giọng-elevenlabs)
11. [Đăng video](#11-đăng-video)
12. [Viết kịch bản bằng tay (định dạng JSON)](#12-viết-kịch-bản-bằng-tay-định-dạng-json)
13. [Mọi thiết lập trong .env](#13-mọi-thiết-lập-trong-env)
14. [Cấu trúc thư mục](#14-cấu-trúc-thư-mục)
15. [Dùng bằng dòng lệnh](#15-dùng-bằng-dòng-lệnh)
16. [Xử lý sự cố](#16-xử-lý-sự-cố)
17. [Giấy phép và bản quyền](#17-giấy-phép-và-bản-quyền)

---

## 1. Cần chuẩn bị gì

| | Tối thiểu | Máy đã dùng để dựng hệ thống |
|---|---|---|
| Hệ điều hành | Linux hoặc Windows 10/11, 64-bit | Windows 11 |
| RAM | 8 GB (đặt `FACTORY_PARALLEL=1`) | 16 GB trở lên, CPU 32 luồng |
| Ổ đĩa trống | ~10 GB (cài thường) — thêm ~25 GB nếu tự vẽ ảnh | |
| Card đồ hoạ | Không cần — **trừ khi tự vẽ ảnh**: NVIDIA RTX, ≥ 8 GB VRAM, driver ≥ 580 | RTX 4060 Laptop 8 GB: ~3 giây/ảnh |
| Mạng | Ổn định (tải ~3 GB khi cài, thêm ~9 GB nếu tự vẽ ảnh) | |

Thời gian cài: 15–30 phút cho phần thường, thêm 30–90 phút (tuỳ mạng) cho công cụ tự vẽ ảnh.

## 2. Đăng ký tài khoản và lấy key

| Dịch vụ | Dùng để | Bắt buộc? | Chi phí |
|---|---|---|---|
| Google AI Studio (Gemini API) | Viết nháp kịch bản, đặt từ khoá / mô tả ảnh cho từng câu, soát ảnh | **Có** | Miễn phí (có hạn mức) |
| Pixabay hoặc Pexels API | Ảnh và clip stock | **Có một trong hai** | Miễn phí |
| GitHub | Tải mã về bằng `git clone` | Nên có | Miễn phí |
| ElevenLabs | Giọng podcast (chỉ bản MoneyPrinterTurbo) | Không | Free (làm tay) / trả phí để tự động |
| TikTok, YouTube | Kênh để đăng video | Tuỳ bạn | Miễn phí |

Không cần tài khoản: giọng đọc Edge TTS, Hugging Face (tải model vẽ ảnh), Wikimedia Commons, ComfyUI.

### Gemini API key (bắt buộc)

1. Mở <https://aistudio.google.com/apikey>, đăng nhập bằng tài khoản Google.
2. Bấm **Create API key** (được hỏi thì cho tạo project mới). Chép chuỗi key — thường bắt đầu bằng `AIza`.
3. Để dành, bước 5 sẽ dán vào `.env`: `GEMINI_API_KEY=<key>`.

Gói miễn phí không cần thẻ, nhưng giới hạn số lần gọi theo phút và theo ngày, giờ cao điểm hay báo quá tải (503) — hệ
thống tự chờ và tự đổi sang model dự phòng, một bản nháp thường mất 1–3 phút. Gói miễn phí **không vẽ ảnh** được (nguồn
ảnh `gemini` cần bật thanh toán; nguồn `comfyui` thì miễn phí). Theo điều khoản của Google, dữ liệu gửi qua gói miễn phí
có thể được dùng để cải thiện sản phẩm — đừng đưa thông tin nhạy cảm vào kịch bản.

### Pixabay API key (ảnh và clip stock)

1. Đăng nhập hoặc đăng ký ở <https://pixabay.com/api/docs/> để lấy API key.
2. Thêm vào `.env`:

```ini
PIXABAY_API_KEY=<key>
IMAGE_SOURCE=pixabay
```

Bốn engine slide dùng ảnh Pixabay theo từng câu. MoneyPrinterTurbo dựng ảnh thành clip zoom,
kể cả bản podcast; engine **Stock khớp lời** lấy video Pixabay (clip ngang được crop nếu thiếu clip dọc).
Kịch bản có thể ghi `"image_source": "pixabay"` hoặc `"pexels"` để đổi nguồn riêng.
Khi dùng ảnh vẽ AI, đặt `STOCK_SOURCE=pixabay` để chọn nguồn stock dự phòng.
API search được cache 24 giờ; ảnh/video tải về máy. Nguồn ảnh được giữ cùng metadata của beat
và `credits.txt`; clip stock có `sources.txt`.
Không cần key Pexels khi chọn Pixabay. Tài khoản Pixabay thông thường cung cấp ảnh tối đa 1280px;
repo dùng `largeImageURL` và không yêu cầu quyền full-resolution.

### Pexels API key (nguồn thay thế)

Pexels đang tạm dừng cấp API key mới; nếu chưa có key, dùng Pixabay ở trên.
Key Pexels có sẵn vẫn dùng được khi đặt `IMAGE_SOURCE=pexels`.

1. Tạo tài khoản ở <https://www.pexels.com/join> (miễn phí).
2. Mở <https://www.pexels.com/api/>, bấm **Your API Key** (lần đầu phải điền mục đích dùng, ví dụ
   "Personal tool that makes short educational videos"), chép key.
3. Để dành cho `.env`: `PEXELS_API_KEY=<key>`.

Hạn mức mặc định: 200 lượt gọi mỗi giờ, 20.000 lượt mỗi tháng — đủ cho vài chục video mỗi ngày. Ảnh và clip Pexels
dùng miễn phí, không bắt buộc ghi nguồn.

### ElevenLabs (tuỳ chọn — chỉ cho bản podcast)

1. Tạo tài khoản ở <https://elevenlabs.io>.
2. **Gói Free**: không cần key. Trên web Video Factory bấm *Làm giọng trên ElevenLabs* — hệ thống chép sẵn lời, mở trang
   Text to Speech; bạn tự chọn giọng, dán, *Generate*, *Download*; file mp3 trong thư mục Downloads được nhận tự động.
3. **Gói trả phí** (Starter trở lên) mới gọi được giọng thư viện qua API (gói Free bị từ chối, lỗi 402). Muốn tự động hoàn
   toàn: *Developers → API Keys → Create*, cấp quyền *Text to Speech* và *Voices: Write*, chép key vào `.env`:
   `ELEVENLABS_API_KEY=<key>`.

Đọc điều khoản của ElevenLabs trước khi đăng video kiếm tiền: gói Free không có quyền dùng thương mại và yêu cầu ghi nguồn.

## 3. Cài phần mềm nền

Mở **PowerShell** (bấm Start, gõ `powershell`) rồi chạy lần lượt — `winget` có sẵn trên Windows 10/11:

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Gyan.FFmpeg -e
winget install --id Google.Chrome -e
winget install --id 7zip.7zip -e
```

| Phần mềm | Để làm gì |
|---|---|
| Git | Tải mã và 3 repo engine |
| uv | Cài Python và thư viện Python (tự tải đúng phiên bản Python, không cần cài Python riêng) |
| Node.js LTS (≥ 22) | HyperFrames, Remotion, AI-auto-generate-video |
| FFmpeg | Ghép video, gắn phụ đề, chuẩn hoá âm lượng |
| Google Chrome | HyperFrames, Remotion, AI-auto chụp khung hình bằng Chrome |

Cài xong **đóng PowerShell và mở cửa sổ mới** (để Windows nhận đường dẫn mới), kiểm tra:

```powershell
git --version; uv --version; node --version; ffmpeg -version
```

## 4. Tải mã và cài đặt

Chọn thư mục **không có dấu cách, không có chữ có dấu, không nằm trong OneDrive** — ví dụ `C:\video-factory`:

```powershell
cd C:\
git clone https://github.com/<tài-khoản>/video-factory.git
cd video-factory
uv run --no-project --python 3.12 python cai-dat.py
```

Installer chạy bằng `uv run --no-project --python 3.12 python cai-dat.py` trên cả Linux và Windows.
Sau khi cài, các lệnh `python` dùng môi trường `.venv` đã kích hoạt (xem mục 6).
Installer Python chạy lại được:

1. kiểm tra Git, uv, Node.js, FFmpeg, Chrome — thiếu thì báo và dừng
2. tạo file `.env` từ `.env.example`; mở bằng editor để điền key
3. cài thư viện Python của web (`uv sync`) và thư viện Node của HyperFrames, Remotion, ELK (`npm ci`)
4. tải 3 repo engine **đúng commit đã chạy thử** vào `engines\` rồi cài thư viện của từng repo:
   MoneyPrinterTurbo (`uv sync`), AI-auto-generate-video (`npm ci`), Pixelle-Video (`uv sync` + Chromium cho Playwright)
5. chép key Gemini / Pexels từ `.env` sang `config.toml` của MoneyPrinterTurbo
6. in tình trạng: key nào đã có, engine nào sẵn sàng

Cuối cùng thấy `[ok]` ở cả 6 engine là xong. Chỉ xem lại tình trạng: `python cai-dat.py --check`.

## 5. Điền key

Mở `.env` (Notepad, nằm ở thư mục gốc) và dán key lấy ở bước 2, **không có dấu cách, không có ngoặc kép**:

```ini
GEMINI_API_KEY=AIza...
PEXELS_API_KEY=...
```

Lưu file rồi **chạy lại `cai-dat.py`** để key được chép sang MoneyPrinterTurbo (lần này chỉ mất vài giây).
`.env` chỉ nằm trên máy bạn và đã có trong `.gitignore` — không bao giờ bị đưa lên GitHub. Các thiết lập khác: [mục 13](#13-mọi-thiết-lập-trong-env).

## 6. Chạy web

Từ thư mục gốc repo, trên Linux:

```bash
source .venv/bin/activate
python chay-web.py
```

Trên Windows PowerShell: `.venv\Scripts\Activate.ps1` rồi `python chay-web.py`.
Hoặc trên cả hai hệ điều hành: `uv run --locked python chay-web.py`.
Trình duyệt tự mở <http://127.0.0.1:8600> khi server sẵn sàng. **Ctrl+C dừng web.**
Báo cổng 8600 đang được dùng nghĩa là web đã chạy ở cửa sổ khác — cứ mở địa chỉ trên.

**Launcher chỉ bật Video Factory.** Nếu chọn giọng VieNeu, cần bật speech API trong terminal riêng theo hướng dẫn
bên dưới và giữ cả hai server chạy trong lúc tạo video.

Các ô engine ở đầu trang: chấm xanh lá là sẵn sàng, chấm vàng là chưa (rê chuột vào để xem lý do).

## 7. Làm video — cách bình thường

Cách bình thường dùng **ảnh và clip Pexels** — không cần card đồ hoạ.

**Bước 1 — có kịch bản**, chọn một trong hai tab:

- **Từ chủ đề**: gõ chủ đề (ví dụ *"Vì sao ta hay nhớ người cũ?"*), chọn **Độ dài** (~1 / 2 / 3 phút) và **Kiểu mở đầu**
  (tò mò, phá niềm tin, danh sách, rủi ro, câu hỏi thi — hoặc để Gemini chọn), ghi chú thêm nếu cần. Tuỳ chọn:
  - *Rà soát kiến thức* — Gemini kiểm lại dữ kiện (dùng Google Search nếu còn hạn mức);
  - *Kèm bản podcast* — viết thêm lời kiểu podcast tâm sự cho MoneyPrinterTurbo ([mục 10](#10-bản-podcast-giọng-elevenlabs));
  - *Chọn góc nhìn 3 vòng* — Gemini nghĩ 12 góc kể, giữ 3, viết 3 đoạn mở đầu rồi chấm cặp; góc thắng thành khung bài (thêm 3 lần gọi).

  Bấm **Nhờ Gemini viết nháp** (1–3 phút). Nháp hiện ra dạng JSON: **đọc lại kỹ** (Gemini có thể sai kiến thức), sửa nếu
  cần, bấm **Lưu thay đổi**. Nháp lưu ở `content/drafts/`.
- **Kịch bản có sẵn**: chọn một file trong `content/` → **Mở kịch bản**. Repo có sẵn vài kịch bản mẫu (tâm lý, kiến thức,
  thiên nhiên, AWS, sơ đồ).

**Bước 2 — tạo video**: tick các engine muốn dùng → **Tạo video**. Mỗi engine là một tác vụ nền (mặc định chạy 2 engine
cùng lúc); cột *Các lần tạo* hiện tiến độ. Nút **Log** xem nhật ký từng engine, **Chạy lại** khi một engine lỗi.

**Bước 3 — chọn bản để đăng**: xem các bản ngay trên trang, bấm **Chọn để đăng** ở bản ưng ý → file video và `caption.txt`
(tiêu đề, mô tả, hashtag, ghi nguồn ảnh nếu có) được chép vào `publish/<lần-tạo>/`. Xem [mục 11](#11-đăng-video).

Ảnh lấy từ Pexels nên đúng "loại cảnh" nhưng không đúng người / vật cụ thể: Pexels tốt với thứ quay được (cảnh vật, đồ
ăn, cảm xúc người), kém với khái niệm trừu tượng ("load balancer" ra… xe tải). Muốn ảnh khớp lời hơn: tự vẽ ([mục 8](#8-tự-tạo-ảnh-bằng-ai-trên-máy));
muốn đúng người thật: Wikimedia Commons ([mục 9](#9-ảnh-thật-cho-người-và-sự-kiện-có-thật)).

### Giọng VieNeu-TTS (tuỳ chọn, chạy trên máy)

Ngoài Edge TTS, bạn có thể chọn **VieNeu-TTS** cho cả 6 engine: video slide/sơ đồ và video ảnh/footage đều dùng được.
Factory gọi [speech API v3 Turbo của VieNeu](https://github.com/pnnbao97/VieNeu-TTS/blob/main/apps/openai_speech.py)
qua mạng cục bộ; không cài model VieNeu vào môi trường của factory. Server cục bộ không cần API key, trừ khi bạn
tự bật xác thực. Việc này không thay thế key Gemini/Pexels cho viết nháp và lấy stock.

**Cài đặt một lần** từ thư mục gốc Video Factory:

```bash
git clone https://github.com/pnnbao97/VieNeu-TTS.git engines/VieNeu-TTS
cd engines/VieNeu-TTS
uv sync
cd ../..
uv sync --locked
```

Nếu đã có checkout VieNeu, dùng thư mục đó thay cho `engines/VieNeu-TTS`; không cần clone lại.
VieNeu có `.venv` riêng và dùng CPU/ONNX trong cấu hình dưới đây. Muốn dùng GPU, làm theo
[hướng dẫn CUDA chính thức](https://github.com/pnnbao97/VieNeu-TTS) trước khi bật server.

**Mỗi lần sử dụng**, mở hai terminal:

Terminal 1 — từ thư mục gốc Video Factory, bật VieNeu trên Linux:

```bash
cd engines/VieNeu-TTS
VIENEU_BACKEND=onnx uv run python -m apps.openai_speech
```

Trên Windows PowerShell, đặt `$env:VIENEU_BACKEND="onnx"` rồi chạy `uv run python -m apps.openai_speech`
trong thư mục VieNeu. Server mặc định ở `http://127.0.0.1:8000`. Đợi server hoàn tất khởi động;
lần đầu tải và nạp model cần thời gian. **Giữ terminal này mở** trong suốt quá trình tạo video.

Terminal 2 — từ thư mục gốc Video Factory, bật web trên Linux:

```bash
source .venv/bin/activate
python chay-web.py
```

Nếu web đã chạy, giữ nguyên terminal của web. Trên web, mở kịch bản → **Giọng đọc video → VieNeu-TTS** →
**Tải lại danh sách giọng** → chọn tên giọng từ gợi ý (ví dụ `Mai Anh`) → **Lưu thay đổi** → **Tạo video**.
Để trống tên giọng dùng `VIENEU_VOICE` trong `.env`, mặc định `Hải Đăng`.

Có thể kiểm tra server từ terminal khác bằng `curl http://127.0.0.1:8000/v1/voices` (khi chưa bật Bearer auth).
Nếu chỉ muốn dùng Edge TTS, chọn Edge trên web; không cần bật server VieNeu.

**Phụ đề:** factory có sẵn faster-whisper và PyAV tương thích. Whisper tải model `small` khi dùng lần đầu,
xử lý trên CPU; mốc các chữ không nhận diện được được nội suy từ chữ khớp gần nhất. Nếu MoneyPrinterTurbo
đã cài, factory ưu tiên môi trường Whisper của engine đó; có thể đặt `ALIGN_PYTHON` trong `.env` tới interpreter
của một môi trường riêng có faster-whisper và `av>=11,<19`. Khi server hoặc Whisper lỗi, sửa nguyên nhân rồi
bấm **Chạy lại** ở engine bị lỗi.

Thiết lập `.env` tuỳ chọn: `VIENEU_URL=http://127.0.0.1:8000`, `VIENEU_VOICE=Hải Đăng`,
`VIENEU_API_KEY=<key server nếu đã bật Bearer auth>`. `VIENEU_URL` cũng nhận URL kết thúc bằng `/v1`.
Đổi server/giọng tạo cache audio riêng. Nếu server hoặc Whisper lỗi, job báo lỗi để bạn sửa và chạy lại.

Kịch bản JSON có thể thêm `"tts_provider": "vieneu", "vieneu_voice": "Mai Anh"`; trường `voice` vẫn giữ giọng Edge
để chuyển lại. Kịch bản cũ không có `tts_provider` tiếp tục dùng Edge. Với podcast MoneyPrinterTurbo,
file giọng tải lên được ưu tiên; nếu không có file, lựa chọn VieNeu được dùng thay ElevenLabs.

## 8. Tự tạo ảnh bằng AI trên máy

Ảnh được tạo bằng [ComfyUI](https://github.com/Comfy-Org/ComfyUI) và model
[SDXL-Lightning 4 bước](https://huggingface.co/ByteDance/SDXL-Lightning). Bản cài Python dùng checkout native
`engines/ComfyUI` và venv riêng, chạy được trên CPU hoặc NVIDIA CUDA. CPU tạo ảnh SDXL chậm;
cho máy GPU tích hợp, ảnh/clip Pexels là lựa chọn nhẹ hơn. Phần này hoàn toàn tuỳ chọn, tách khỏi VieNeu.
Áp dụng cho MoneyPrinterTurbo, AI-auto, HyperFrames, Pixelle, Remotion; engine stock dùng clip Pixabay hoặc Pexels theo nguồn đã chọn.

### 8.1 Cài (một lần)

```bash
python cai-comfyui.py --device cpu
python chay-comfyui.py
```

Installer tải ComfyUI v0.38.0 từ GitHub, cài PyTorch CPU và requirements trong venv riêng, rồi tải checkpoint
`sdxl_lightning_4step.safetensors` (~7 GB) vào `engines/ComfyUI/models/checkpoints/`. File tải dở được tải tiếp;
installer so kích thước và SHA-256 trước khi đưa model vào dùng. Không cần 7-Zip hoặc bản portable Windows.
Dùng `--skip-model` nếu chỉ muốn cài ComfyUI; dùng `--device cuda` khi có NVIDIA và driver tương thích CUDA 13.
Launcher lưu và dùng lại thiết bị đã chọn. Bản portable Windows đã cài từ trước vẫn được launcher hỗ trợ.

### 8.2 Dùng khi làm video

1. Chạy **`python chay-comfyui.py`**, chờ dòng `To see the GUI go to: http://127.0.0.1:8188`. **Để cửa sổ này mở** suốt lúc
   tạo video (đóng là tắt ComfyUI).
2. Chọn nguồn ảnh — một trong hai cách:
   - cho **một kịch bản**: thêm vào đầu file JSON (cùng cấp với `"title"`): `"image_source": "comfyui",`
   - cho **mọi video**: thêm vào `.env`: `IMAGE_SOURCE=comfyui`
3. Tạo video như bình thường. Ảnh đầu tiên mất ~10 giây (nạp model vào card), sau đó ~3 giây/ảnh (RTX 4060 8 GB).
   ComfyUI chưa bật thì hệ thống dùng nguồn stock dự phòng (`STOCK_SOURCE`).

Cách hệ thống vẽ: Gemini đọc từng câu và viết một mô tả cảnh tiếng Anh → ComfyUI vẽ ảnh dọc 768×1344 (4 bước, cfg 1,
euler, sgm_uniform) → ảnh được phóng thành nền 1080×1920, zoom chậm, đổi sớm hơn lời 0,35 giây. Bản MoneyPrinterTurbo
băm theo vế câu, đổi hình ~2,2 giây một lần. Ảnh lưu trong `.cache/beats/ai/` — chạy lại cùng kịch bản không phải vẽ lại.

### 8.3 Điều khiển nội dung ảnh

Thêm vào kịch bản (tất cả tuỳ chọn, viết bằng tiếng Anh cho Gemini và SDXL hiểu đúng):

| Trường | Ý nghĩa | Ví dụ |
|---|---|---|
| `image_note` | Lời dặn Gemini khi viết mô tả cảnh: chủ thể, thứ phải có / không có | `"Pure untouched nature only: forests, water, sky, wild animals. No people."` |
| `image_mood` | Ánh sáng và màu chung cho cả video (chỉ là phong cách, không phải chủ thể) | `"misty morning, soft pastel colours"` |
| `image_forbid` | Thứ **không được** xuất hiện: vẽ xong Gemini soát cả loạt ảnh, ảnh vi phạm được vẽ lại (tối đa 3 lượt, lượt sau chuyển sang cận cảnh). Hiện chỉ bản MoneyPrinterTurbo soát | `"people, footpaths, roads, buildings, fences"` |
| `images` | `false` = tắt ảnh nền (vd. video nhiều sơ đồ) | `false` |

Mặc định (không có `image_note`) người trong ảnh là người Việt trẻ. Ví dụ đầy đủ:
[`content/thien-nhien/20-phut-thien-nhien.json`](content/thien-nhien/20-phut-thien-nhien.json) — video thiên nhiên không
có người, không có công trình. SDXL-Lightning không có "prompt phủ định" (cfg 1) và hay tự vẽ lối mòn trong rừng —
`image_forbid` chính là để bắt lỗi này; vẫn nên xem lại ảnh trước khi đăng.

**Không vẽ người có thật bằng AI** (chính trị gia, người nổi tiếng…): ảnh chỉ "giống", dễ bị hiểu nhầm là ảnh thật. Video
về người thật dùng ảnh thật — [mục 9](#9-ảnh-thật-cho-người-và-sự-kiện-có-thật).

### 8.4 Vẽ ảnh lẻ, không làm video

Bật `chay-comfyui.py`, rồi ở thư mục gốc:

```powershell
python vf-python.py -m factory.ve_anh "a misty lotus pond at dawn, soft golden light" -n 4
python vf-python.py -m factory.ve_anh "hồ sen buổi sớm có sương" --dich -n 4
```

Ảnh dọc 768×1344 lưu ở `anh-ve\<ngày-giờ>-<mô-tả>\` kèm `prompt.txt`. SDXL hiểu tiếng Anh tốt hơn hẳn tiếng Việt —
viết tiếng Việt thì thêm `--dich` để Gemini viết lại thành mô tả tiếng Anh.

Hoặc dùng giao diện của ComfyUI: mở <http://127.0.0.1:8188> → workflow mặc định → ở nút *Load Checkpoint* chọn
`sdxl_lightning_4step.safetensors` → *KSampler*: steps **4**, cfg **1.0**, sampler **euler**, scheduler **sgm_uniform** →
*Empty Latent Image*: 768 × 1344 (dọc) hoặc 1344 × 768 (ngang) → gõ mô tả vào ô prompt dương → **Queue / Run**.
Ảnh nằm trong `engines/ComfyUI/output/` (hoặc `engines/ComfyUI_windows_portable/ComfyUI/output/` nếu dùng bản portable đã cài trước).

## 9. Ảnh thật cho người và sự kiện có thật

Video nói về một người, một sự kiện cụ thể (ví dụ [`content/kien-thuc/trump-nhiem-ky-dau.json`](content/kien-thuc/trump-nhiem-ky-dau.json))
thì đặt `"image_source": "commons"`: hệ thống lấy **ảnh thật trên Wikimedia Commons**, chỉ nhận giấy phép tự do (tài sản
công, CC0, CC BY, CC BY-SA). Ảnh cần ghi nguồn được liệt kê trong `credits.txt` và **tự nối vào caption** khi chọn bản.

Hiện **chỉ engine MoneyPrinterTurbo** dùng ảnh Commons — các engine khác gặp `commons` vẫn lấy ảnh Pexels (sai người,
sai sự kiện), nên với kịch bản loại này chỉ tick MoneyPrinterTurbo.

- **Tự động**: Gemini đặt truy vấn cho từng câu (tên người phải có trong tên ảnh, năm sự kiện), hệ thống lọc năm chụp ±1
  và cho Gemini duyệt. Đúng khoảng 85–90% — đủ cho bản nháp, **chưa đủ** cho video chính trị / thời sự.
- **Ghim tay** cho đúng 100%: tìm ảnh trên <https://commons.wikimedia.org>, chép tên file (dạng `File:….jpg`) vào kịch bản:

  ```json
  "image_pins": [
    {"match": "Bốn năm đầu ở Nhà Trắng", "files": ["File:A rainbow is seen over the North Portico of the White House, Saturday, May 11, 2024.jpg"]},
    {"match": "tuyên bố rút khỏi Hiệp định khí hậu Paris", "files": ["File:….jpg", "File:….jpg"]}
  ]
  ```

  `match` là một đoạn trong lời đọc; vế câu chứa đoạn đó dùng đúng các file đã ghim, mỗi file một cảnh. Không tìm được
  ảnh thật cho một ý thì sửa lời cho khớp ảnh có thật, đừng dùng ảnh "gần đúng".
- Wikimedia giới hạn tần suất tải: hệ thống tải chậm (≥ 1 giây/lần); lấy không đủ ảnh thì job **báo lỗi** — bấm *Chạy lại*
  sau vài phút (ảnh đã tải được giữ lại).

Nội dung chính trị nên trung lập, chỉ nêu dữ kiện kiểm chứng được.

## 10. Bản podcast giọng ElevenLabs

Chủ đề tâm lý, tình yêu hợp kiểu **podcast tâm sự** (văn nói, xưng "mình", một ý cảm xúc). Chỉ bản MoneyPrinterTurbo dùng.

1. Tick *Kèm bản podcast* khi viết nháp, hoặc mở kịch bản có sẵn rồi bấm **Viết bản podcast** — Gemini viết thêm phần
   `podcast` (tiêu đề, lời thoại ~70 giây, từ khoá clip nền).
2. Chọn **giọng podcast**: Mai (nữ, Hà Nội) hoặc Nhật Phong (nam) — giọng tổng hợp có sẵn trong thư viện ElevenLabs.
3. Làm giọng, theo một trong ba cách:
   - **Gói Free**: bấm **Làm giọng trên ElevenLabs** → trên trang vừa mở: chọn giọng → `Ctrl+V` → *Generate* → *Download*.
     Web tự nhận file mp3 mới trong Downloads (chờ tối đa 20 phút). Nhật Phong dùng được ở gói Free; Mai thì không.
   - **Tải file giọng lên**: file mp3 bạn tự thu hoặc tải từ đâu đó — miễn đúng lời podcast.
   - **Gói trả phí + `ELEVENLABS_API_KEY`**: không cần làm gì, hệ thống tự đọc.
4. Tick MoneyPrinterTurbo → **Tạo video**. Whisper nghe lại file giọng để căn phụ đề karaoke khớp từng chữ (lần đầu tải model
   Whisper ~500 MB).

Không có cả ba thì bản podcast đọc bằng giọng Edge HoaiMy. Hệ thống không tự bấm trên web ElevenLabs thay bạn (điều khoản
của ElevenLabs cấm công cụ tự động).

## 11. Đăng video

Sau khi **Chọn để đăng**, thư mục `publish/<lần-tạo>/` có file video `<tên-video>.mp4` (dọc 1080×1920) và
`caption.txt` (dán vào ô mô tả khi đăng).

- **Nhạc nền**: video xuất ra chỉ có giọng đọc và hiệu ứng âm thanh tự tổng hợp. Thêm nhạc trong trình đăng của TikTok /
  YouTube Shorts (thư viện nhạc đã được cấp phép cho nền tảng đó) là an toàn nhất. Muốn nhạc nằm sẵn trong video: bỏ file
  nhạc bạn có quyền dùng (vd. YouTube Audio Library) vào `assets/music/` (bản podcast: `assets/music/podcast/`).
  **Đừng dùng kho nhạc có sẵn của MoneyPrinterTurbo** (`resource/songs`): một bản trong đó đã bị Content ID nhận và YouTube
  chặn Short trên toàn cầu.
- **Nhãn nội dung AI**: video dùng ảnh tự vẽ trông như ảnh thật thì bật nhãn *AI-generated* (TikTok) hoặc khai báo nội dung
  bị thay đổi / tổng hợp (YouTube) khi đăng.
- **Ghi nguồn**: ảnh Wikimedia Commons đã có sẵn trong `caption.txt`; giữ nguyên khi đăng.

## 12. Viết kịch bản bằng tay (định dạng JSON)

Kịch bản là một file JSON trong `content/` (thư mục con tuỳ ý). Định nghĩa đầy đủ: [`factory/spec.py`](factory/spec.py).
Ví dụ tối thiểu:

```json
{
  "id": "vi-sao-troi-xanh",
  "title": "Vì sao bầu trời màu xanh?",
  "voice": "vi-VN-HoaiMyNeural",
  "stock_terms": ["blue sky", "sunset clouds", "sunlight"],
  "description": "Ánh sáng mặt trời và hiện tượng tán xạ Rayleigh.",
  "hashtags": ["khoahoc", "vatly"],
  "scenes": [
    {"type": "title", "say": "Bầu trời không hề có màu. Vậy vì sao ta lại thấy nó xanh?",
     "headline": [["VÌ SAO TRỜI", false], ["MÀU XANH?", true]], "sub": "Tán xạ Rayleigh"},
    {"type": "bullets", "say": "Ánh sáng trắng gồm nhiều màu. Ánh xanh có bước sóng ngắn nên bị không khí tán xạ mạnh nhất.",
     "heading": "Ánh sáng bị tán xạ",
     "items": [{"text": "Ánh trắng = nhiều màu", "cue": "nhiều màu"}, {"text": "Xanh tán xạ mạnh nhất", "cue": "tán xạ mạnh nhất"}]},
    {"type": "next", "say": "Lưu lại để giải thích cho bạn bè nhé.", "title": "Lưu lại để ôn"}
  ]
}
```

**Trường chung**

| Trường | Ý nghĩa |
|---|---|
| `id`, `title` | Mã (không dấu, nối bằng gạch ngang) và tiêu đề video |
| `voice` | Giọng Edge: `vi-VN-HoaiMyNeural` (nữ, mặc định) hoặc `vi-VN-NamMinhNeural` (nam) |
| `scenes` | Danh sách cảnh (bảng dưới) |
| `stock_terms` | Từ khoá tiếng Anh tìm clip nền chung (MoneyPrinterTurbo, dự phòng cho các engine khác) |
| `description`, `hashtags` | Nội dung cho `caption.txt` |
| `series`, `ep`, `total` | Tuỳ chọn, cho video theo series ("Tập 3/31") |
| `image_source`, `image_note`, `image_mood`, `image_forbid`, `image_pins`, `images` | Nguồn và nội dung ảnh — [mục 8](#83-điều-khiển-nội-dung-ảnh), [mục 9](#9-ảnh-thật-cho-người-và-sự-kiện-có-thật) |
| `podcast` | Bản podcast — [mục 10](#10-bản-podcast-giọng-elevenlabs) (thường do Gemini viết) |

**Loại cảnh** — mọi cảnh có `say` (lời đọc), tuỳ chọn `kicker` (nhãn nhỏ trên tiêu đề) và `stock` (1–2 từ khoá clip
riêng cho cảnh). `cue` là một cụm **có trong lời đọc**: thành phần hiện ra đúng lúc cụm đó được đọc.

| `type` | Trường bắt buộc | Dùng cho |
|---|---|---|
| `title` | `headline`: `[[chữ, tô_màu], …]` (+ `tag`, `sub`, `chips`) | Mở đầu |
| `bullets` | `heading`, `items`: `[{text, cue}]` | Danh sách ý |
| `compare` | `heading`, `left`, `right`: `{title, points: []}` | So sánh hai vế |
| `stat` | `stats`: `[{value, label, cue}]` (+ `heading`) | Con số lớn |
| `flow` | `heading`, `nodes` (+ `groups`, `edges`, `steps`) | Sơ đồ tự dàn bố cục — xem [`factory/flow.py`](factory/flow.py), ví dụ [`content/demo/flow-demo.json`](content/demo/flow-demo.json) |
| `diagram` | `diagram`, `heading` (+ `events`) | Sơ đồ toạ độ soạn tay, khai báo trong `diagrams` |
| `tip` | `question`, `answer` (+ `answer_cue`) | Mẹo / câu hỏi thi |
| `next` | `title` (+ `sub`) | Kết, hẹn tập sau |

Mẹo: viết số và thuật ngữ đúng như muốn thấy trên phụ đề; tránh ký hiệu `/ % &` vì giọng đọc có thể đọc sai.

## 13. Mọi thiết lập trong .env

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `GEMINI_API_KEY` | — | **Bắt buộc**. Key Gemini |
| `PIXABAY_API_KEY` | — | Key Pixabay; dùng cùng `IMAGE_SOURCE=pixabay` |
| `PEXELS_API_KEY` | — | Key Pexels; dùng nếu chọn Pexels |
| `GEMINI_MODEL` | `gemini-flash-latest` | Model Gemini; quá tải thì tự thử model dự phòng |
| `ELEVENLABS_API_KEY` | — | Giọng podcast qua API (gói trả phí) |
| `ELEVENLABS_VOICE` | `mai` | `mai`, `nhatphong` hoặc một `voice_id` trong thư viện ElevenLabs |
| `IMAGE_SOURCE` | `pexels` | Nguồn ảnh cho mọi video: `pixabay`, `pexels`, `comfyui`, `gemini`, `commons` (kịch bản đặt `image_source` thì kịch bản thắng) |
| `COMFYUI_URL` | `http://127.0.0.1:8188` | Địa chỉ ComfyUI (đổi nếu chạy ComfyUI ở máy khác trong mạng) |
| `FACTORY_PARALLEL` | `2` | Số engine render cùng lúc (RAM 8 GB nên để `1`) |
| `MPT_DIR` | `engines\MoneyPrinterTurbo` | Chỗ cài MoneyPrinterTurbo nếu bạn đã có sẵn ở nơi khác |
| `CHROME_PATH` | tự tìm Chrome, không có thì Edge | Đường dẫn `chrome.exe` |

Đổi `.env` xong: tắt web (đóng cửa sổ) rồi bật lại `chay-web.py`; đổi key Gemini / Pexels thì chạy lại `cai-dat.py`.

## 14. Cấu trúc thư mục

```
video-factory/
├─ cai-dat.py           cài đặt (setup/install.py)
├─ cai-comfyui.py       cài công cụ tự vẽ ảnh (setup/comfy.py)
├─ chay-web.py          bật web, cổng 8600
├─ chay-comfyui.py      bật ComfyUI, cổng 8188
├─ vf-python.py         chạy Python của dự án (mục 15)
├─ .env.example          mẫu thiết lập — cai-dat.py chép thành .env
├─ factory/              mã chính: web, hàng đợi, kịch bản, giọng đọc, ảnh, phụ đề
│  ├─ engines/           6 engine (mỗi engine một file)
│  └─ web/               giao diện
├─ engines/
│  ├─ hyperframes-academic/   template HyperFrames (trong repo)
│  ├─ remotion-academic/      project Remotion (trong repo)
│  ├─ MoneyPrinterTurbo/      ┐
│  ├─ ai-auto-generate-video/ │ cai-dat.py tải về (không nằm trong repo)
│  ├─ pixelle-video/          ┘
│  └─ ComfyUI/           cai-comfyui.py tải về (tùy chọn)
├─ content/              kịch bản (JSON); content/drafts/ là nháp Gemini viết
├─ assets/               nhạc nền của bạn (assets/music/), ảnh đại diện kênh mẫu
├─ tools/elk/            dàn bố cục sơ đồ (ELK)
├─ docs/                 ghi chú kỹ thuật, so sánh các engine, khảo sát xu hướng TikTok
├─ examples/aws-saa-series/   series 31 tập ôn thi AWS SAA-C03 làm bằng MoneyPrinterTurbo
├─ runs/                 kết quả từng lần tạo (tự sinh)
├─ publish/              bản đã chọn để đăng (tự sinh)
└─ anh-ve/               ảnh vẽ lẻ bằng factory.ve_anh (tự sinh)
```

## 15. Dùng bằng dòng lệnh

Mở terminal ở thư mục gốc. `vf-python.py` chạy Python của dự án (giống `python`, kể cả khi Smart App Control chặn
launcher của venv — xem mục 16):

```powershell
python vf-python.py -m factory.status                                          # tình trạng key, engine, ComfyUI
python vf-python.py -m factory.try_engine hyperframes content/aws-saa/ep05.json # chạy thử một engine, không cần web
python vf-python.py -m factory.preview content/demo/flow-demo.json             # xem nhanh vài khung hình (không render)
python vf-python.py -m factory.ve_anh "a red fox in snow" -n 2                 # vẽ ảnh lẻ (cần ComfyUI)
```

Tên engine: `mpt`, `broll`, `aiauto`, `hyperframes`, `pixelle`, `remotion`. Kết quả `try_engine` ở `.cache\try\<engine>\`.

## 16. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| `cai-dat.py` báo thiếu phần mềm dù vừa cài | Đóng cửa sổ, mở lại (Windows chưa nhận PATH mới); vẫn thiếu thì khởi động lại máy |
| "An Application Control policy has blocked this file", lỗi 4551 | **Smart App Control** của Windows 11 chặn file không ký số (xem bên dưới) |
| Engine chấm vàng trên web | Rê chuột lên ô engine xem lý do; thường là chưa chạy hết `cai-dat.py` hoặc thiếu key |
| Gemini báo 503 / 429, viết nháp lâu | Gói miễn phí quá tải hoặc hết hạn mức: hệ thống tự chờ / đổi model. Hết hạn mức ngày thì đợi hôm sau |
| Pexels lỗi 429 | Quá 200 lượt/giờ — đợi một lúc rồi *Chạy lại* |
| VieNeu báo `Connection refused` / "không phản hồi" | Bật speech API trong terminal riêng, đợi khởi động xong; kiểm tra `VIENEU_URL` trỏ tới đúng máy/cổng |
| Whisper báo thiếu `faster_whisper` | Chạy `uv sync --locked` ở thư mục Video Factory; nếu đặt `ALIGN_PYTHON`, kiểm tra phụ thuộc trong môi trường đó |
| Whisper báo `metadata_errors` | Môi trường Whisper cần `faster-whisper==1.2.1` và `av>=11,<19`; chạy `uv sync --locked` cho factory hoặc cài bộ phiên bản này trong môi trường `ALIGN_PYTHON`/MoneyPrinterTurbo đang dùng |
| "không gọi được ComfyUI" | Chưa bật `chay-comfyui.py` (hoặc đã đóng cửa sổ của nó) |
| ComfyUI báo lỗi CUDA / không thấy GPU | Driver NVIDIA < 580 → cập nhật driver, khởi động lại máy |
| `chay-comfyui.py` báo `WinError 4551 … torch\lib\…dll` | Smart App Control chặn PyTorch — xem ghi chú bên dưới |
| ComfyUI báo hết bộ nhớ (out of memory) | Đóng game / ứng dụng dùng card; card < 8 GB VRAM có thể không đủ cho SDXL |
| MoneyPrinterTurbo lỗi ở bước audio | Edge TTS thỉnh thoảng chậm / treo → *Chạy lại* |
| Wikimedia Commons báo lỗi thiếu ảnh | Bị giới hạn tần suất → *Chạy lại* sau vài phút |
| Phụ đề mất dấu tiếng Việt (web MoneyPrinterTurbo) | Chọn font `BeVietnamPro-Bold.ttf`; đừng bấm "Khôi phục cài đặt phụ đề" |
| Báo cổng 8600 đang được dùng | Web đã chạy ở cửa sổ khác — mở <http://127.0.0.1:8600> |
| Lỗi lạ với đường dẫn | Chuyển thư mục về chỗ không dấu cách / không dấu tiếng Việt / ngoài OneDrive, chạy lại `cai-dat.py` |

**Smart App Control.** Ở chế độ bật, Windows 11 chặn dần các file thực thi không có chữ ký số. Trên máy dựng hệ thống nó
đã chặn launcher `.venv\Scripts\python.exe` mà uv tạo cho mọi venv, `uvicorn.exe`, ffmpeg đi kèm Remotion, và Python tạm
uv dùng khi build thư viện. Repo đã tự né cả mấy chỗ đó — **không cần tắt Smart App Control**:
`vf-python.py` và [`factory/pyrun.py`](factory/pyrun.py) chạy Python gốc do uv cài (có chữ ký) kèm thư viện của venv;
Remotion chỉ xuất khung hình rồi ghép bằng FFmpeg của hệ thống; Pixelle được build ngay trong venv. Riêng PyTorch của
ComfyUI thì không né được. Nếu gặp chặn ở chỗ khác: Event Viewer → *Applications and Services Logs → Microsoft → Windows → CodeIntegrity → Operational* cho biết file
nào bị chặn. Chi tiết: [`docs/ghi-chu-ky-thuat.md`](docs/ghi-chu-ky-thuat.md#smart-app-control-windows-11).

## 17. Giấy phép và bản quyền

| Thành phần | Giấy phép | Ghi chú |
|---|---|---|
| Mã của video-factory (thư mục này) | Tác giả giữ bản quyền | Chưa kèm giấy phép mở |
| [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | MIT | Tải về khi cài, không chép vào repo |
| [AI-auto-generate-video](https://github.com/huytranvan2010/AI-auto-generate-video) | MIT | Tải về khi cài |
| [Pixelle-Video](https://github.com/ATH-MaaS/Pixelle-Video) | Apache-2.0 | Tải về khi cài |
| [HyperFrames](https://www.npmjs.com/package/hyperframes) | Apache-2.0 | Gói npm |
| [Remotion](https://www.remotion.dev/license) | Giấy phép riêng | Miễn phí cho cá nhân và công ty ≤ 3 người; lớn hơn phải mua license |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI) | GPL-3.0 | Tải về khi cài |
| [SDXL-Lightning](https://huggingface.co/ByteDance/SDXL-Lightning) | CreativeML OpenRAIL++-M | Có điều khoản cấm dùng vào mục đích gây hại |
| [edge-tts](https://github.com/rany2/edge-tts) | LGPL-3.0 | Dùng dịch vụ đọc của Microsoft Edge (không chính thức) |
| [elkjs](https://github.com/kieler/elkjs) | EPL-2.0 | Dàn bố cục sơ đồ |
| [diagrams](https://github.com/mingrammer/diagrams) | MIT | Kèm bộ icon AWS (theo điều khoản AWS Architecture Icons) |
| Font Be Vietnam Pro | SIL Open Font License 1.1 | `engines/*/fonts`, `examples/aws-saa-series/studio/fonts` |
| Ảnh / clip Pexels | [Pexels License](https://www.pexels.com/license/) | Miễn phí, không bắt buộc ghi nguồn; không bán lại nguyên bản |
| Ảnh Wikimedia Commons | Theo từng file | Hệ thống chỉ lấy giấy phép tự do và tự ghi nguồn vào caption |

Nhạc: chỉ dùng nhạc bạn có quyền dùng. Giọng ElevenLabs: theo điều khoản của gói bạn dùng.

---

Tài liệu thêm: [ghi chú kỹ thuật](docs/ghi-chu-ky-thuat.md) · [đánh giá ưu / nhược từng engine](docs/danh-gia-cac-repo-video.docx) ·
[khảo sát xu hướng TikTok 09/2026](docs/xu-huong-tiktok-2026-09.md) · [so sánh hình ảnh các engine](docs/so-sanh-01-10/)

## Chỉnh sửa Remotion bằng Qwen

Mở một lần tạo đã hoàn tất → **Chỉnh sửa** trên thẻ Remotion. Đánh dấu hai mốc
thời gian hoặc chọn một cảnh, nhập yêu cầu và đính kèm ảnh nếu cần. Trình chỉnh sửa
hiển thị toàn bộ các cảnh sẽ thay đổi trước khi gửi. Các mốc chọn được mở rộng ra
các cảnh giao nhau; không sửa riêng một phần giây bên trong cảnh.

Ví dụ: “Thay tiêu đề bằng ‘Origami trong vũ trụ’, dùng ảnh đính kèm làm nền và
cho các ý xuất hiện lần lượt. Giữ nguyên lời đọc.” Có thể yêu cầu đổi lời đọc,
thay kiểu cảnh hoặc chia một cảnh thành nhiều cảnh. Khi lời đọc thay đổi, VieNeu
phải đang chạy; thời lượng và toàn bộ mốc phụ đề/cảnh phía sau được tính lại.
Ảnh và chữ có thể dùng các hiệu ứng fade, slide, zoom, stagger; không tạo video
hay hình ảnh mới bằng AI.

Cấu hình riêng trong `.env` (không đưa key lên Git):

```dotenv
EDITOR_LLM_BASE_URL=<base URL OpenAI-compatible của nhà cung cấp, kết thúc /v1>
EDITOR_LLM_API_KEY=<API key Qwen>
EDITOR_LLM_MODEL=qwen3.7-plus
```

Endpoint cần hỗ trợ Chat Completions, JSON object response, `enable_thinking=false`
và image input khi dùng ảnh tham khảo. Có thể đổi model sang một model Qwen khác
mà nhà cung cấp hỗ trợ. Lỗi chỉnh sửa không tự chuyển sang Gemini. Các chức năng
viết nháp/tìm ảnh hiện có vẫn dùng cấu hình Gemini riêng. Yêu cầu thay ảnh stock
cần key Pixabay/Pexels; ảnh tải lên không cần key stock. Chỉ gửi nội dung cảnh và
ảnh đính kèm cho Qwen, không gửi toàn bộ MP4.

Mỗi lần chỉnh sửa tạo bản xem thử riêng. **Dùng phiên bản này** chọn nguồn cho lần
sửa tiếp theo; có thể chọn lại Video gốc để hoàn tác. **Chọn bản này để đăng** mới
cập nhật thư mục `publish/`. Thử lại lỗi render dùng kế hoạch đã lưu, không gọi lại
Qwen; lỗi diễn giải có thể cần một lần gọi API mới. Đóng/mở cửa sổ không làm mất
lịch sử. Không dùng **Chạy lại** Remotion sau khi đã mở trình chỉnh sửa; thao tác đó
bị chặn để bảo vệ nguồn và lịch sử.

Nguồn chỉnh sửa lưu ở `runs/<job>/editor/`; các bản render mới giữ ảnh và giọng ở
`runs/<job>/remotion/sources/`. Với video cũ, editor tìm lại ảnh từ nguồn đã lưu
hoặc bản HyperFrames cùng job khi metadata trùng khớp, và trích giọng từ MP4 gốc.
Thiếu ảnh sẽ có thông báo yêu cầu thay ảnh cho cảnh đó. Giữ nguyên thư mục job và
nguồn media; không xóa các thư mục này nếu muốn tiếp tục chỉnh sửa. Bản đầu tiên
render lại toàn bộ video, nên thời gian dựng gần với Remotion bình thường.

Kiểm tra API thực tế, chỉ gọi Qwen và xác minh kế hoạch:

```bash
python -m factory.editor_smoke --job 20261010-131144-origami-khoa-hoc-vu-tru --api-only
```

Dựng một bản xem thử bằng kế hoạch Qwen, không tự chọn/đăng:

```bash
python -m factory.editor_smoke --job 20261010-131144-origami-khoa-hoc-vu-tru --render
```

Kiểm tra tự động: `python -m unittest discover -s tests -p 'test_*.py'`,
`node tests/test_editor_ui.cjs`, `node tests/test_editor_workflow.cjs`,
`node tests/test_editor_remotion.cjs`, `node tests/test_tts_ui.cjs` và
`engines/remotion-academic/node_modules/.bin/tsc --noEmit -p engines/remotion-academic/tsconfig.json`.
Các bài kiểm tra server/Chrome cần môi trường cho phép tạo socket và khởi động
trình duyệt; live Qwen cần mạng ra ngoài. Kiểm tra editor bằng dữ liệu mẫu không
phát sinh phí API.
