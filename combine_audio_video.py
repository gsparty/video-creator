from moviepy.editor import VideoFileClip, AudioFileClip

def replace_audio(video_path, audio_path, output_path):
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)

    # Sync video length with audio
    final_video = video.set_audio(audio).subclip(0, min(video.duration, audio.duration))
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")

if __name__ == "__main__":
    replace_audio(
        video_path="raw_video.mp4",           # generic placeholder
        audio_path="final_audio.mp3",         # generic placeholder
        output_path="final_video.mp4"
    )
