"""One-shot CPU speech worker, adapted from PromptetheusBot's speech_output.py."""
import os

# Keep the separate speech process light enough to run alongside local AI models.
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import io
import json
import logging
import sys
import wave
from pathlib import Path

LANGS = {'a': 'en-us', 'b': 'en-gb', 'e': 'es', 'f': 'fr-fr', 'h': 'hi', 'i': 'it',
         'j': 'ja', 'p': 'pt-br', 'z': 'cmn'}


def session(model, threads):
    import onnxruntime as rt
    options = rt.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    return rt.InferenceSession(model, sess_options=options, providers=['CPUExecutionProvider'])


def kokoro_wav(text, values):
    import numpy as np
    from kokoro_onnx import Kokoro
    logging.getLogger('phonemizer').setLevel(logging.ERROR)
    model = Kokoro.from_session(session(values['speech_kokoro_model'], values['speech_threads']),
                                values['speech_kokoro_voices'])
    voice = values['speech_voice']
    samples, rate = model.create(text, voice=voice, speed=values['speech_speed'],
                                 lang=LANGS.get(voice[0], 'en-us'))
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype('<i2')
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())
    return out.getvalue()


def piper_wav(text, values, folder):
    from piper.voice import PiperVoice
    from piper.config import PiperConfig, SynthesisConfig
    model = values['speech_piper_model']
    config = PiperConfig.from_dict(json.loads(Path(model + '.json').read_text(encoding='utf-8')))
    voice = PiperVoice(session=session(model, values['speech_threads']), config=config,
                       download_dir=Path(folder))
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        voice.synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=1.0 / values['speech_speed']))
    return out.getvalue()


def synthesize(text, values, folder):
    fallback = False
    if values['speech_engine'] == 'kokoro':
        try:
            return kokoro_wav(text, values), 'kokoro', False
        except Exception:
            logging.exception('Kokoro failed; trying Piper')
            fallback = True
    return piper_wav(text, values, folder), 'piper', fallback


def main():
    request = json.load(sys.stdin)
    output = Path(sys.argv[1])
    audio, engine, fallback = synthesize(request['text'], request['settings'], output.parent)
    output.write_bytes(audio)
    output.with_suffix('.json').write_text(json.dumps({'engine': engine, 'fallback': fallback}), encoding='utf-8')


if __name__ == '__main__':
    main()
