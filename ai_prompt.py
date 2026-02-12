from openai import OpenAI
from config import OPENAI_API_KEY

client=OpenAI(api_key=OPENAI_API_KEY)


def gen_story(prompt):
    story_prompt=f'''Make a funny satirical vivid story(100-200 words) based on the prompt:{prompt}. Make it suitable fro a social media reel narration.'''
    response = client.chat.completions.create(
        model="gpt-4o",

    messages=[
        {"role": "system", "content": "You are a creative storyteller."},
        {"role": "user","content": story_prompt},
    ],
    temperature=0.8,max_tokens=500
    )

    story = response.choices[0].message.content.strip()


    return story