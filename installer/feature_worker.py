"""Run one optional feature smoke test in an isolated CPU process."""
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def offline():
    def blocked(*args, **kwargs):
        raise OSError("Feature tests are offline; install all required assets before testing.")
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"


def sample_speech(folder):
    path = folder / "spoken-question.wav"
    quoted = "'" + str(path).replace("'", "''") + "'"
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$v=$s.GetInstalledVoices()|Where-Object {$_.VoiceInfo.Culture.Name -like 'en-*'}|Select-Object -First 1; "
        "try { if($v){$s.SelectVoice($v.VoiceInfo.Name)}; $s.SetOutputToWaveFile(" + quoted + "); "
        "$s.Speak('What is the capital of France?') } finally {$s.Dispose()}")
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], check=True, timeout=60,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return path


def run(feature, values, folder):
    sys.path.insert(0, str(ROOT))
    from app import config, settings
    candidate = {**config.DEFAULTS, **values}
    settings.load = lambda: dict(candidate)  # This child only; no real settings are changed.
    offline()
    if feature == "whisper":
        from app.tools import speech_to_text
        path = sample_speech(folder)
        text, _ = speech_to_text.transcribe(path.read_bytes(), ".wav")
        normalized = text.lower()
        if "capital" not in normalized or "france" not in normalized:
            raise RuntimeError("Test transcription did not recognize the sample: " + text)
        return {"transcript": text}
    if feature in ("kokoro", "piper"):
        from app.tools import speech, speech_worker
        if feature == "kokoro":
            data = speech_worker.kokoro_wav("Hello. Your local voice is working.", candidate)
        else:
            data = speech_worker.piper_wav("Hello. Your local voice is working.", candidate, folder)
        speech.validate_wav(data)
        (folder / "speech-test.wav").write_bytes(data)
        return {"audio_bytes": len(data)}
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (640, 160), "white")
    draw = ImageDraw.Draw(image)
    if feature == "ocr":
        from app.tools import scan
        draw.text((25, 40), "HELLO WORLD 42", fill="black", font=ImageFont.load_default(size=48))
        out = io.BytesIO()
        image.save(out, format="PNG")
        _, text, _ = scan.read_photo(out.getvalue())
        if "HELLO" not in text.upper() or "WORLD" not in text.upper():
            raise RuntimeError("OCR did not recognize the generated sample: " + text)
        return {"text": text}
    if feature == "vision":
        from app.tools import vision
        image = Image.new("RGB", (256, 256), "white")
        ImageDraw.Draw(image).ellipse((35, 35, 220, 220), fill="blue")
        out = io.BytesIO()
        image.save(out, format="PNG")
        answer = vision.ask(out.getvalue(), "Name the color of the circle. Answer in one word.", candidate)
        if "blue" not in answer.lower():
            raise RuntimeError("Vision did not identify the generated sample: " + answer[:300])
        return {"answer": answer[:300]}
    if feature == "image":
        from app.tools import imagine
        data = imagine.generate("a simple blue circle on a plain white background", "quick", candidate, seed=42)
        with Image.open(io.BytesIO(data)) as result:
            if result.format != "PNG" or result.size != (256, 256):
                raise RuntimeError("Image generation returned invalid output.")
        (folder / "image-test.png").write_bytes(data)
        return {"image_bytes": len(data)}
    raise ValueError("Unknown feature: " + feature)


def main():
    request_path = Path(sys.argv[1])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    output = request_path.with_name("result.json")
    try:
        details = run(request["feature"], request["settings"], request_path.parent)
        result = {"status": "passed", "details": details}
        code = 0
    except Exception as exc:
        import traceback
        traceback.print_exc()
        result = {"status": "failed", "error": str(exc)}
        code = 1
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
