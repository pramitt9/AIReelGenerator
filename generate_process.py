
import os
from text_to_audio import text_to_speech_file
from ai_prompt import gen_story
import time
import subprocess

def text_to_audio(folder):
    print("TTA - ", folder)
    desc_path=f"user_uploads/{folder}/desc.txt"
    if not os.path.exists(desc_path):
        print("No description file found." )
        return
    with open(desc_path,'r',encoding="utf-8") as f:
        user_prompt=f.read().strip()
        print("user_prompt= ",user_prompt)

    story=gen_story(user_prompt)
    if not story or not isinstance(story, str):
        print("⚠️ No story generated, using original prompt.")
        story = user_prompt
    print("Generated story: ", story)

    with open(f"user_uploads/{folder}/story.txt","w",encoding="utf-8") as f:
        f.write(story)
    

    text_to_speech_file(story,folder)


def create_reel(folder):
    command=f'''ffmpeg -f concat -safe 0 -i user_uploads/{folder}/input.txt -i user_uploads/{folder}/audio.mp3 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black" -c:v libx264 -c:a aac -shortest -r 30 -pix_fmt yuv420p static/reels/{folder}.mp4'''
    subprocess.run(command,shell=True,check=True)
    print("CR - ",folder)


if __name__=="__main__":
    while True:
        print("Processing queue...")
        with open("done.txt","r") as f:
            done_folders=f.readlines()
        
        done_folders=[f.strip() for f in done_folders]
        folders=os.listdir("user_uploads")
        for folder in folders:
            if(folder not in done_folders):
                text_to_audio(folder)
                create_reel(folder)
                with open("done.txt","a") as f:
                    f.write(folder + "\n")
        time.sleep(4)