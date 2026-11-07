# Social Video Studio

A local-first production workspace for creating FINOMICS videos. The application runs on your own computer and stores projects and uploaded media in a local data directory.

## Current capabilities

- Local projects and media asset library.
- Upload video, audio, image and SRT subtitle assets.
- Select and order video clips for an export.
- Trim each clip using start and end times.
- Standard cuts or sequential video crossfades (0.2 to 2.5 seconds).
- One voiceover track and one looping background-music track, with volume and fade controls.
- Burn SRT subtitles into the video with classic white, bold white or yellow styling, at the bottom or centre.
- Export vertical 1080 × 1920 or landscape 1920 × 1080 H.264 MP4 at 24, 30 or 60 FPS.
- Background export queue with status polling and restart recovery.
- API-key protected local browser interface and API.

This is an editing and assembly foundation, not yet a complete AI video-generation studio. It does not currently provide a visual multitrack timeline, waveform editing, clip-level audio crossfades, generated scenes, animated charts, automatic transcription, or direct ChatGPT control.

## Requirements

- Windows 10/11, macOS or Linux.
- Python 3.11 or 3.12. CI currently tests Python 3.12.
- FFmpeg and FFprobe installed and available on PATH.
- For burned-in subtitles, use an FFmpeg build that includes the `subtitles` filter and libass.
- A strong local API key.

Hugging Face credentials are only needed for the optional image/video generation endpoints. Local editing and export do not require a Hugging Face token or paid API.

## Windows quick start

### 1. Install FFmpeg

Install a reputable Windows FFmpeg build that includes FFprobe and the libass subtitle filter. Add the folder containing `ffmpeg.exe` and `ffprobe.exe` to your Windows PATH, then open a new PowerShell window.

Verify:

```powershell
ffmpeg -version
ffprobe -version
ffmpeg -filters | Select-String subtitles
```

The final command should show the `subtitles` filter. If it does not, choose a build with libass enabled. FFmpeg build licensing varies with compile-time options. Review the exact build's licence before redistribution.

### 2. Download the project

```powershell
git clone https://github.com/bbrokade-spec/social-video-studio.git
cd social-video-studio
```

Use the approved branch or pull request containing the features you want to test. The default `main` branch may not yet contain the open draft work.

### 3. Create the Python environment

You can run the setup helper, which creates the virtual environment, installs requirements, copies `.env.example` when needed and creates the local data directory:

```powershell
.\\scripts\\setup_windows.ps1
```

Or perform the steps manually:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks environment activation, use a Command Prompt window and run:

```bat
.venv\Scripts\activate.bat
```

### 4. Configure the local API key

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

Set a long, unique random value for `API_KEY` in `.env`. Keep `ALLOW_UNAUTHENTICATED_GENERATION=false`. You may leave `HF_TOKEN` blank if you are only using local editing and export.

Do not share the API key or commit the `.env` file.

### 5. Check and start the application

Run the preflight check to confirm Python, FFmpeg, FFprobe, the subtitle filter and API key are configured:

```powershell
.\\scripts\\check_windows.ps1
```

Then launch the server with the loopback-only helper:

```powershell
.\\scripts\\run_windows.ps1
```

Or start it manually:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) and enter the same API key. Keep the server bound to `127.0.0.1`. Do not expose it to the internet or a public network.

API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Export workflow

1. Create or select a project.
2. Upload source video, audio and optional SRT files.
3. Select video clips in the order they should appear.
4. Set optional in/out trim points for each clip.
5. Choose standard cuts or crossfades and set the duration.
6. Optionally select one voiceover and one background music track.
7. Set audio levels and fade durations.
8. Optionally select an SRT file and subtitle style/position.
9. Choose vertical or landscape output and frame rate.
10. Start the export. The interface polls the background job and downloads the completed MP4.

### Current editing constraints

- Crossfade is a video transition. Audio tracks are mixed over the overall output timeline; source clip audio is not crossfaded between clips.
- Crossfade requires at least two clips. Every trimmed clip must be longer than the selected transition duration.
- SRT subtitle times refer to the final assembled timeline. Reordering or trimming clips may require you to adjust the SRT timings yourself.
- One voiceover and one music track are supported. Music loops to cover the output; voiceover starts at the beginning and is not automatically looped.
- Export output is H.264 video with AAC audio when audio is selected.
- The local export worker is designed for one application process and one worker against a data directory. Do not run multiple Uvicorn workers against the same database and media folder.
- A forced process termination during export can leave a partial file. Restart recovery requeues interrupted jobs.

## Data and privacy

Project database, uploaded assets and exports are stored under `DATA_DIR` (default: `./data`). Back up this directory if you need to retain projects. Treat it as private because it contains your uploaded media and rendered videos.

Do not commit the `data` directory, credentials, private media or exports to Git.

## Optional Hugging Face generation

The repository also contains adapters for the configured Z-Image-Turbo and Wan 2.2 Hugging Face Spaces. These are separate from local editing/export and depend on third-party service availability, quotas, temporary output URLs and the provider's current API contract. Configure `HF_TOKEN` only if you intend to use those generation routes.

## Development checks

```powershell
python -m compileall -q app tests
python -m pytest -q
```

The GitHub Actions workflow runs these checks on Python 3.12. Passing CI verifies the Python tests and compilation, not actual FFmpeg rendering on your Windows computer.

## Security notes

- Keep `API_KEY` and `HF_TOKEN` out of source control.
- Keep the server bound to loopback unless you have deliberately configured HTTPS, network access controls and stronger deployment protections.
- The application is a local development tool. It is not yet hardened for public multi-user hosting.
- Review the licence of the exact FFmpeg binary you install, especially before distributing a packaged application.
