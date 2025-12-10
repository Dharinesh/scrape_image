#img_gen.py
import re
import os
import openai
from openai import OpenAI
import base64
from typing import List, Dict
from datetime import datetime

class ImageContentParser:
    """
    Parse product image layouts from text file and return structured data.
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.content = self._read_file()
    
    def _read_file(self) -> str:
        """Read the content from the file."""
        try:
            with open(os.path.normpath(self.file_path), 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            return ""
    
    def parse_images_to_list(self) -> List[Dict]:
        """
        Parse product image layouts and return as structured list.
        
        Returns:
            List[Dict]: List where each element contains one image's structured data
        """
        if not self.content:
            return []
        
        # Split content by image sections - updated pattern for your format
        image_sections = re.split(r'🟩\s*\*\*Image\s+(\d+)\s*–\s*([^*]+)\*\*', self.content)
        
        # Remove the first empty section if it exists
        if len(image_sections) > 1 and not image_sections[0].strip():
            image_sections = image_sections[1:]
        
        images_list = []
        
        # Process triplets of (image_number, title, content)
        for i in range(0, len(image_sections), 3):
            if i + 2 < len(image_sections):
                image_number = image_sections[i].strip()
                title = image_sections[i + 1].strip()
                image_content = image_sections[i + 2]
                
                image_dict = self._parse_single_image(image_number, title, image_content)
                images_list.append(image_dict)
        
        print(f"Parsed {len(images_list)} images")
        return images_list
    
    def _parse_single_image(self, image_number: str, title: str, image_content: str) -> Dict:
        """Parse a single image's content into structured data."""
        
        # Extract the full image generation prompt
        prompt_match = re.search(r'\*\*Image Generation Prompt:\*\*\s*\n(.*?)(?=\n\n---|$)', image_content, re.DOTALL)
        full_prompt = prompt_match.group(1).strip() if prompt_match else image_content.strip()
        
        # Extract headline from the prompt
        headline_patterns = [
            r'headline[:\s]*["\']([^"\']+)["\']',
            r'headline[:\s]*"([^"]+)"',
            r'headline[:\s]*([^.!?]+[.!?])',
        ]
        
        headline = ""
        for pattern in headline_patterns:
            match = re.search(pattern, full_prompt, re.IGNORECASE)
            if match:
                headline = match.group(1).strip()
                break
        
        # Extract key visual elements
        visual_elements = self._extract_visual_elements_from_prompt(full_prompt)
        
        # Extract any quoted text (user testimonials, etc.)
        quotes = re.findall(r'"([^"]{10,})"', full_prompt)
        
        # Extract statistics/percentages
        stats = re.findall(r'(\d+%[^.]*)', full_prompt)
        
        return {
            'image_number': image_number,
            'title': title,
            'full_prompt': full_prompt,
            'headline': headline,
            'visual_elements': visual_elements,
            'quotes': quotes,
            'statistics': stats,
            'icons': [],
            'copy_elements': [],
            'key_data': stats,
            'mobile_optimization': ['Mobile optimized', 'High contrast text', 'Bold readable fonts']
        }
    
    def _extract_visual_elements_from_prompt(self, prompt: str) -> List[str]:
        """Extract visual elements from the full prompt."""
        visual_elements = []
        
        # Look for common visual descriptors
        visual_keywords = [
            'show', 'display', 'feature', 'include', 'create', 'place', 'add',
            'vibrant', 'professional', 'clean', 'modern', 'dramatic', 'step-by-step'
        ]
        
        sentences = re.split(r'[.!?]', prompt)
        for sentence in sentences:
            sentence = sentence.strip()
            if any(keyword in sentence.lower() for keyword in visual_keywords):
                if len(sentence) > 10 and len(sentence) < 100:
                    visual_elements.append(sentence)
        
        return visual_elements[:5]  # Limit to 5 elements
    
    def _extract_subtext(self, content: str) -> str:
        """Extract subtext from content."""
        # For the new format, subtext is usually in the supporting text or descriptions
        subtext_patterns = [
            r'supporting text[^:]*:\s*["\']([^"\']+)["\']',
            r'below[^:]*:\s*["\']([^"\']+)["\']',
            r'callout[^:]*:\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in subtext_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""
    
    def _extract_copy_elements(self, content: str) -> List[str]:
        """Extract copy elements from content."""
        copy_elements = []
        
        # Extract bullet points
        bullets = re.findall(r'•\s*([^\n•]+)', content)
        copy_elements.extend([bullet.strip() for bullet in bullets])
        
        # Extract numbered lists
        numbered = re.findall(r'\d+\.\s*([^\n\d]+)', content)
        copy_elements.extend([item.strip() for item in numbered])
        
        return copy_elements
    
    def _extract_key_data(self, content: str) -> List[str]:
        """Extract key data from content."""
        key_data = []
        
        # Extract percentages and numbers
        percentages = re.findall(r'(\d+%[^.\n]*)', content)
        key_data.extend(percentages)
        
        # Extract comparison data
        comparisons = re.findall(r'(vs?\.\s*\d+%[^.\n]*)', content)
        key_data.extend(comparisons)
        
        return key_data
    
    def _extract_mobile_optimization(self, content: str) -> List[str]:
        """Extract mobile optimization from content."""
        mobile_elements = []
        
        # Look for mobile-specific mentions
        if 'mobile' in content.lower():
            mobile_elements.append("Mobile optimized design")
        if 'readable' in content.lower():
            mobile_elements.append("High readability")
        if 'bold' in content.lower():
            mobile_elements.append("Bold text elements")
        
        return mobile_elements if mobile_elements else ["Mobile optimized"]
    
    def get_formatted_content_list(self) -> List[str]:
        """
        Get a list of formatted content strings for each image.
        
        Returns:
            List[str]: List of formatted content strings
        """
        images = self.parse_images_to_list()
        content_list = []
        
        # Visual/aesthetic keywords to append
        visual_keywords = (
            "Photorealistic product render, Bright, clean white background, Soft shadows, Minimalist composition, "
            "Mobile-optimized layout, Modern sans-serif font, Natural lighting, Professional studio style, "
            "Lifestyle integration, Elegant iconography, Color-accented sections (e.g., gold tones, gentle creams, brand colors), "
            "High contrast for text readability."
        )
        
        for img in images:
            # Use the full prompt as the primary content
            content = img['full_prompt']
            # Append the visual keywords (not replace)
            content_with_keywords = f"{content}\n\nVisual Style Keywords: {visual_keywords}"
            content_list.append(content_with_keywords)
        
        return content_list


class HighQualityImageGenerator:
    """
    Generate high-quality images using OpenAI's DALL-E API.
    """
    
    def __init__(self, api_key: str):
        openai.api_key = api_key
        self.client = OpenAI(api_key=api_key)
        self.output_dir = "generated_images"
        self._create_output_directory()
    
    def _create_output_directory(self):
        """Create output directory if it doesn't exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def _clean_content(self, content: str) -> str:
        """Clean and optimize content for image generation."""
        # Remove formatting characters
        content = content.replace("**", "").replace("*", "")
        
        # Remove extra newlines and spaces
        content = re.sub(r'\n+', ' ', content).strip()
        content = re.sub(r'\s+', ' ', content)
        
        # Remove structural elements
        content = re.sub(r'IMAGE \d+:', '', content)
        content = re.sub(r'=+', '', content)
        
        # Limit length for API constraints (DALL-E has a 1000 char limit)
        if len(content) > 900:
            content = content[:900] + "..."
        
        return content
    
    def _create_optimized_prompt(self, content: str) -> str:
        """Create an optimized prompt for high-quality image generation."""
        cleaned_content = self._clean_content(content)
        
        # Enhanced prompt for better quality with specific requirements
        prompt = f"""You are a professional Amazon product listing image generator.
                Your task is to generate a professional Amazon product listing image based on the provided content.
                The image should be a high-quality, professional marketing image with clean modern design, white background, bold readable text optimized for mobile viewing.
                The image should be visually rich, branded, and fits marketing standards. The image should clearly convey the product's advantages and be suitable for both digital and print media.
                Use times new roman font for the text to maintain a professional appearance strictly!
                
                Create a professional Amazon product listing image: 
                this is how the image should have: {cleaned_content}

                
                Style: High-quality, professional marketing image with clean modern design, white background, bold readable text optimized for mobile viewing.
                Strictly include real people in the image to enhance relatability and emotional connection.
                I want the alignments to be perfectly made.
                Everything mention in the content should be given in the image.
                Everything should be fit into the image.
                No breaking of the content!
                No compromise!!
                """
        
        return prompt
    
    def generate_image(self, content: str, image_index: int) -> List[str]:
        """
        Generate high-quality images using OpenAI streaming API with partial images.
        
        Args:
            content (str): Content for image generation
            image_index (int): Index of the image
            
        Returns:
            List[str]: List containing path to the final high-quality generated image file
        """
        try:
            cleaned_content = self._clean_content(content)
            
            print(f"🎨 Generating image {image_index + 1}...")
            print(f"📝 Content: {cleaned_content[:100]}...")
            
            # Create streaming request with partial images for high quality
            stream = self.client.responses.create(
                model="gpt-4.1",
                input=cleaned_content,
                stream=True,
                tools=[{"type": "image_generation", "partial_images": 2}],
            )
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            generated_files = []
            final_image_data = None
            max_partial_index = -1
            
            # Process all events to find the final/highest quality image
            for event in stream:
                if event.type == "response.image_generation_call.partial_image":
                    idx = event.partial_image_index
                    image_base64 = event.partial_image_b64
                    image_bytes = base64.b64decode(image_base64)
                    
                    # Keep track of the highest index (final image)
                    if idx > max_partial_index:
                        max_partial_index = idx
                        final_image_data = image_bytes
                    
                    print(f"📥 Processing partial image {idx}...")
            
            # Save only the final high-quality image
            if final_image_data:
                filename = f"amazon_product_image_{image_index+1}_{timestamp}.png"
                filepath = os.path.join(self.output_dir, filename)
                
                with open(filepath, "wb") as f:
                    f.write(final_image_data)
                
                print(f"✅ High-quality image saved: {filepath}")
                return [filepath]
            else:
                print(f"❌ No final image data received for index {image_index+1}")
                return []
                
        except Exception as e:
            print(f"❌ Error generating image for index {image_index+1}: {e}")
            return []
    
    def generate_all_images(self, content_list: List[str]) -> List[str]:
        """
        Generate all images from content list using DALL-E API.
        
        Args:
            content_list (List[str]): List of content for each image
            
        Returns:
            List[str]: List of paths to all generated image files
        """
        all_generated_images = []
        
        print(f"🚀 Starting generation of {len(content_list)} images...")

        for i, content in enumerate(content_list):
            print(f"\n📸 Processing image {i+1}/{len(content_list)}...")
            
            image_files = self.generate_image(content, i)
            all_generated_images.extend(image_files)
        
        print(f"\n🎉 Successfully generated {len(all_generated_images)} total images!")
        return all_generated_images



def main():
    """
    Main function to run the complete image generation pipeline.
    """
    
    # Configuration - UPDATE THESE VALUES
    API_KEY = "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"  # OpenAI API key
    FILE_PATH = "D:\\college\\Profit_Story\\task4(2)\\task4\\B07VSSQRMJ\\amazon_images_final.txt"  # Path to your paste.txt file

    try:
        # Step 1: Parse content from file
        print("🔄 Step 1: Parsing content from file...")
        parser = ImageContentParser(FILE_PATH)
        content_list = parser.get_formatted_content_list()
        
        if not content_list:
            print("❌ No content found in file!")
            return
        
        print(f"✅ Found {len(content_list)} images to generate")
        
        # Step 2: Generate high-quality images
        print("\n🔄 Step 2: Generating high-quality images...")
        generator = HighQualityImageGenerator(API_KEY)
        generated_images = generator.generate_all_images(content_list)
        
        if not generated_images:
            print("❌ No images were generated!")
            return
    
        print(f"\n📂 All generated images can be found in: {generator.output_dir}")
        
    except Exception as e:
        print(f"❌ Error in main execution: {e}")


if __name__ == "__main__":
    main()
