import os
import sys
from dotenv import load_dotenv
load_dotenv(".env")
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    result = client.models.generate_images(
        model='imagen-3.0-generate-001',
        prompt='A dark fantasy castle, glassmorphism style',
        config=types.GenerateImagesConfig(
            number_of_images=1,
            output_mime_type="image/jpeg",
            aspect_ratio="1:1"
        )
    )
    for i, generated_image in enumerate(result.generated_images):
        # determine what generated_image.image actually is
        print(type(generated_image.image))
        print("image_bytes exists:", hasattr(generated_image.image, "image_bytes"))
        
except Exception as e:
    print("Error:", e)
