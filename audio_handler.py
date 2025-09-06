import librosa
import soundfile as sf
import numpy as np

def clean_audio(input_path: str, output_path: str):
    # Load audio
    y, sr = librosa.load(input_path, sr=None)

    # Step 1: Remove background noise (simple spectral gating)
    y_reduced = librosa.effects.preemphasis(y)

    # Step 2: Normalize volume
    peak = np.max(np.abs(y_reduced))
    if peak > 0:
        y_normalized = y_reduced / peak * 0.95  # normalize to -1 dBFS
    else:
        y_normalized = y_reduced

    # Step 3: Optional - Compress dynamic range (louder quiet parts)
    y_compressed = librosa.effects.percussive(y_normalized)

    # Save processed audio
    sf.write(output_path, y_compressed, sr)
    print(f"✅ Cleaned audio saved to {output_path}")

if __name__ == "__main__":
    clean_audio("final:audio.flav.mp3", "cleaned_audio.wav")
