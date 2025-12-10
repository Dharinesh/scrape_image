# review_image_generator.py - Fully Automated Version with Image Generation Integration

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
import json
import os
import time

# Import the scraping classes from combined.py
from combined import AmazonReviewsScraper

# Import image generation classes (we'll need to create these)
try:
    from img_gen import ImageContentParser, HighQualityImageGenerator
    IMAGE_GEN_AVAILABLE = True
except ImportError:
    print("⚠️ Image generation modules not found. Only image suggestions will be available.")
    IMAGE_GEN_AVAILABLE = False

class CSVAnalyzerInput(BaseModel):
    """Input schema for CSV analysis"""
    csv_path: str = Field(..., description="Path to the CSV file")
    query: str = Field(..., description="Analysis query or instruction")

class ReliableCSVAnalyzer(BaseTool):
    """Custom tool that actually works with CSV data using pandas"""
    name: str = "csv_analyzer"
    description: str = "Analyze CSV data using pandas with reliable results"
    args_schema: Type[BaseModel] = CSVAnalyzerInput

    def _run(self, csv_path: str, query: str) -> str:
        """Execute CSV analysis with pandas"""
        try:
            # Read CSV file
            df = pd.read_csv(csv_path)
            total_rows = len(df)
            columns = list(df.columns)

            # Create comprehensive analysis
            analysis_results = {
                "total_rows": total_rows,
                "columns": columns,
                "data_sample": df.head(3).to_dict('records'),
                "column_info": {}
            }

            # Analyze each column
            for col in columns:
                col_info = {
                    "type": str(df[col].dtype),
                    "unique_values": int(df[col].nunique()),
                    "null_count": int(df[col].isnull().sum()),
                    "sample_values": df[col].dropna().head(5).tolist()
                }
                analysis_results["column_info"][col] = col_info

            # Handle specific queries
            query_lower = query.lower()

            # Rating analysis
            if "rating" in query_lower or "star" in query_lower:
                rating_cols = [col for col in columns if any(term in col.lower() for term in ['rating', 'star', 'score'])]
                if rating_cols:
                    rating_col = rating_cols[0]
                    rating_analysis = {
                        "rating_distribution": df[rating_col].value_counts().to_dict(),
                        "average_rating": float(df[rating_col].mean()),
                        "total_ratings": int(df[rating_col].count())
                    }
                    analysis_results["rating_analysis"] = rating_analysis

            # Text analysis for reviews
            if "review" in query_lower or "comment" in query_lower:
                text_cols = [col for col in columns if any(term in col.lower() for term in ['review', 'comment', 'text', 'content'])]
                if text_cols:
                    text_col = text_cols[0]
                    rating_cols = [col for col in columns if any(term in col.lower() for term in ['rating', 'star', 'score'])]
                    if rating_cols:
                        rating_col = rating_cols[0]
                        review_samples = {}
                        for rating in sorted(df[rating_col].unique()):
                            samples_series = df[df[rating_col] == rating][text_col]
                            if isinstance(samples_series, np.ndarray):
                                samples_series = pd.Series(samples_series)
                            samples = pd.Series(samples_series).dropna().head(3).tolist()
                            review_samples[f"{rating}_star"] = samples
                        analysis_results["review_samples"] = review_samples
                    else:
                        analysis_results["review_samples"] = {
                            "random_samples": df[text_col].dropna().head(10).tolist()
                        }

            # Keyword analysis
            if "keyword" in query_lower or "search" in query_lower:
                keywords = [word for word in query.split() if len(word) > 3 and word.lower() not in ['keyword', 'search', 'find', 'look', 'for']]
                if keywords:
                    text_cols = [col for col in columns if any(term in col.lower() for term in ['review', 'comment', 'text', 'content'])]
                    if text_cols:
                        text_col = text_cols[0]
                        keyword_results = {}
                        for keyword in keywords:
                            matches = df[df[text_col].str.contains(keyword, case=False, na=False)]
                            matches_series = matches[text_col]
                            if isinstance(matches_series, np.ndarray):
                                matches_series = pd.Series(matches_series)
                            samples = pd.Series(matches_series).head(3).tolist()
                            keyword_results[keyword] = {
                                "count": len(matches),
                                "percentage": round((len(matches) / total_rows) * 100, 2),
                                "samples": samples
                            }
                        analysis_results["keyword_analysis"] = keyword_results

            # Convert to readable format
            result = f"""
CSV Analysis Results for: {csv_path}

BASIC INFO:
- Total rows: {total_rows}
- Columns: {', '.join(columns)}

DETAILED ANALYSIS:
{json.dumps(analysis_results, indent=2)}

SUMMARY:
This CSV contains {total_rows} records with {len(columns)} columns.
Main data types found: {', '.join(set(str(df[col].dtype) for col in columns))}
"""
            return result
        except Exception as e:
            return f"Error analyzing CSV {csv_path}: {str(e)}"

# Create the custom tool instances
csv_analyzer = ReliableCSVAnalyzer()

# Define Agents
review_analyst = Agent(
    role='Comprehensive CSV Review Analyst',
    goal='Analyze positive and critical reviews from CSV files to identify unique, contextual competitor pain points and real-world product advantages, focusing only on high-helpful-vote reviews and delivering a differentiated 2-column table of pain points and counter-benefits.',
    backstory="""You are an expert at analyzing comprehensive customer review data from CSV files. You excel at processing large volumes of reviews, prioritizing those with high helpful votes (indicating high engagement and relevance), and identifying patterns that reveal true, contextual pain points and differentiated advantages. You focus on:
    - Extracting only meaningful, specific complaints from competitor critical reviews that are unique to their product/brand and not generic to the category.
    - Excluding all generic, expected, or surface-level feedback (e.g., 'bad packaging', 'too expensive', 'durable', 'easy to use', 'looks nice', scent, affordability, shipping, etc.).
    - From your product's positive reviews, surfacing only real-world advantages such as effectiveness in specific use cases, solutions for certain user profiles/environments, switching behavior from competitors, and niche functionality that directly addresses competitor weaknesses.
    - Delivering the output as a 2-column table: 'Customer Complaint on Competitor Product' and 'How Our Product Benefits Users', ensuring every row presents a differentiated pain point and counter-benefit, with no repetition of generic or obvious points.
    You use CSV search tools to analyze every review in the dataset, including review text, ratings, helpful votes, reviewer details, and variant-specific feedback, and you focus on actionable insights that represent true competitive advantages and practical use cases for product variants.""",
    verbose=True,
    allow_delegation=False,
    tools=[csv_analyzer]
)

context_analyst = Agent(
    role='Contextual Analysis Expert',
    goal='Generate clear, non-repetitive context for product strengths and competitor weaknesses based on review analysis',
    backstory="""You are a contextual analysis expert who synthesizes comprehensive review data into clear, actionable insights. Your focus is on creating unique, non-repetitive content that highlights your product's strengths and competitor weaknesses without overlapping with image specifications. You ensure that each point is distinct and adds value to the overall understanding of the product's market position.""",
    verbose=True,
    allow_delegation=False,
    tools=[]
)

image_strategist = Agent(
    role='Visual Marketing Strategist',
    goal='Create non-repetitive, strategic visual specifications for high-conversion Amazon listing images based on unique competitor weaknesses and beginner-friendly variant explanations',
    backstory="""You are a visual marketing expert who transforms unique competitor pain points and variant details into compelling, conversion-focused Amazon listing images with ZERO content repetition. You specialize in strategically distributing unique selling points and variant explanations across different images, ensuring each image serves a distinct purpose without overlapping content. For variants, you craft beginner-friendly, salesperson-like explanations that highlight practical use cases. You understand that modern shoppers quickly scroll through images, so each must deliver unique value and information that builds upon the previous ones.""",
    verbose=True,
    allow_delegation=False,
    tools=[]
)

creative_director = Agent(
    role='Creative Director & Content Distribution Specialist',
    goal='Create 7 unique Amazon listing images with zero repetition, including a beginner-friendly variant explanation in a salesperson-like tone',
    backstory="""You are a creative director who specializes in content distribution strategy for Amazon listings. Your expertise is ensuring ZERO repetition across all images - no repeated headlines, benefits, features, or visual elements. You create a content hierarchy where each image builds upon the previous one with completely new information, including a beginner-friendly, salesperson-style explanation of product variants that highlights practical use cases. You understand that repetitive content reduces conversion rates and wastes valuable image real estate. In addition, for every image prompt you create, you always use and emphasize the following visual and stylistic keywords to ensure the image is visually appealing, modern, and conversion-optimized:
    - Photorealistic product render
    - Bright, clean white background
    - Soft shadows
    - Minimalist composition
    - Mobile-optimized layout
    - Modern sans-serif font
    - Natural lighting
    - Professional studio style
    - Lifestyle integration
    - Elegant iconography
    - Color-accented sections (e.g., gold tones, gentle creams, brand colors)
    - High contrast for text readability
    You ensure that all text and content on the image is short, nice, catchy, and visually attractive, with every word and visual element serving a clear purpose and contributing to the image's appeal.""",
    verbose=True,
    allow_delegation=False,
    tools=[]
)

image_content_quality_checker = Agent(
    role='Image Content Quality Checker',
    goal='Ensure all Amazon image prompts are clean, neat, short, catchy, visually clear, and strictly follow all content rules',
    backstory="""You are a meticulous Amazon image content quality checker. Your job is to review all generated image prompts and ensure they are:
    1. Clean, neat, short, and catchy (including subtext).
    2. All font color instructions are subtle and readable (add as a design instruction if missing).
    3. No user review quotes or content are included in any image.
    4. Comparison is only present in Image 7 (Comprehensive Comparison).
    5. No statistics or percentages are included in any image.
    6. The word 'competitor' is not included in any image.
    If any requirement is not met, you must flag the issue and suggest a correction. You are especially strict about catchiness and clarity of all text, and you always add a note about subtle, readable font color in the design section if missing.""",
    verbose=True,
    allow_delegation=False,
    tools=[]
)

# Define Tasks
def create_analyze_csv_reviews_task():
    return Task(
        description="""
Comprehensively analyze ALL reviews from both CSV files for {product_name}, focusing ONLY on reviews with helpful votes (high engagement/relevance) and including variant-specific feedback if available.

**Step 1: Analyze YOUR product positive reviews CSV**
Use csv_analyzer to extract and analyze ALL positive review data from your product CSV at {your_csv_path}, but only include reviews with helpful votes.

**Step 2: Analyze COMPETITOR critical reviews CSV**
Use csv_analyzer to extract and analyze ALL critical review data from competitor CSV at {competitor_csv_path}, but only include reviews with helpful votes.

**Step 3: Identify and filter insights**
- From competitor’s critical reviews, identify unique and meaningful customer complaints that are:
  • Specific to the competitor’s product or brand
  • Reflect real, contextual pain points (not generic dissatisfaction)
  • Not likely to appear across every product in the category
- From your product’s positive reviews, identify real-world advantages, such as:
  • Product effectiveness in specific use cases
  • Solutions for certain user profiles or environments
  • Switching behavior from competing products
  • Niche functionality that directly addresses competitor weaknesses
- Exclude all generic or expected feedback, such as:
  • Basic quality statements (“good,” “bad,” “works fine”)
  • Surface-level issues (“bad packaging,” “melts fast,” “too expensive”)
  • Universal product expectations (“durable,” “easy to use,” “looks nice”)
  • Obvious features like lathering, scent, affordability, or shipping

**Step 4: Deliverable Table**
- Deliver the output in a 2-column table, formatted as:
  Customer Complaint on Competitor Product | How Our Product Benefits Users
- Ensure every row presents a differentiated pain point and counter-benefit.
- Avoid repeating anything that’s too generic, obvious, or common across all products in the same category.

**Step 5: (If variants provided)**
- Include variant-specific complaints and counter-benefits in the table, focusing on practical use cases and real-world scenarios.

**Step 6: Save and summarize**
- Save the table to '{product_id}/1.comparison_table.txt'

Strictly do not include the packaging details as a metric!
- Summarize the number of reviews analyzed for each product and the filtering criteria used.
""",
        agent=review_analyst,
        expected_output="""
- 2-column table: 'Customer Complaint on Competitor Product' | 'How Our Product Benefits Users', with only unique, contextual, and differentiated points (no generic/obvious feedback)
- Each row must present a real pain point and a counter-benefit
- No repetition of generic, expected, or surface-level issues
- Variant-specific insights included if provided
- Table saved to '{product_id}/1.comparison_table.txt'
- Summary of number of reviews analyzed and filtering criteria used
""",
        tools=[csv_analyzer],
        output_file='{product_id}/1.comparison_table.txt'
    )

def create_context_analysis_task():
    return Task(
        description="""
Based on the dual CSV review analysis, generate context for {product_name} under the following headings:
- Why our product?
- What complaints they have on other products?
- How our product solves the other product problem?

**Instructions:**
- Use the comparison table and unique competitor weaknesses from the review analysis
- Prioritize insights from high helpful vote reviews
- Include variant-specific feedback with practical use cases if {variants} is provided
- Provide specific, quantified examples from CSV data
- Ensure no content overlaps with image specifications
- Save output to '{product_id}/2.complains and why our product.txt'

**Output Format:**
# Why Our Product?
[Detailed reasons based on your product's strengths from CSV analysis, focusing on high helpful vote reviews. Include variant preferences and their practical use cases (e.g., "ideal for X scenario") if applicable]

# What Complaints They Have on Other Products?
[Specific competitor weaknesses from CSV analysis, with quotes and percentages from high helpful vote reviews. Include variant-specific complaints and scenarios if applicable]

# How Our Product Solves the Other Product Problem?
[Clear explanations of how your product addresses each competitor weakness, backed by CSV data. Include variant-specific solutions with practical use cases if applicable]
""",
        agent=context_analyst,
        expected_output="""
Context analysis with:
- Clear, non-repetitive reasons under each heading
- Specific competitor weaknesses backed by CSV data
- Solutions tied to your product's strengths
- Variant-specific insights with practical use cases if provided
- Saved to '{product_id}/2.complains and why our product.txt'
- No overlap with image content
""",
        output_file='{product_id}/2.complains and why our product.txt'
    )

def create_amazon_image_strategy_task():
    return Task(
        description="""
Based on the dual CSV review analysis and context analysis, create a strategic content distribution plan for 7 Amazon listing images.

**CRITICAL NO-REPETITION & NO-REVIEWS/COMPARISON RULES:**
- Each image must contain completely different content
- No repeated headlines, benefits, features, or visual elements
- Each image serves a distinct strategic purpose
- Content builds progressively without overlap
- Use comparison table, context analysis, and variant information to inform content
- **Do NOT include any customer review quotes or content in Images 2–6 or 8.**
- **Do NOT include any 'Us vs Competitor' comparison in Images 2–6 or 8.**
- **All competitor comparison and review quotes must be strictly limited to Image 7.**

**Strategic Image Distribution Framework:**
**Image 2 – Primary Hero Advantage**
- Focus: The #1 most significant unique competitor weakness from CSV analysis (NO review quotes or competitor comparison)
- Content: Main competitive advantage only
- Purpose: Grab attention with strongest differentiator

**Image 3 – Usability Excellence**
- Focus: Unique ease-of-use advantages (if competitor has usability issues from CSV, but NO direct comparison or review quotes)
- Content: How-to/setup simplicity that competitor lacks
- Purpose: Show superior user experience

**Image 4 – Performance Results**
- Focus: Unique performance/outcome advantages from CSV data (NO review quotes or competitor comparison)
- Content: Results and benefits competitor can't deliver
- Purpose: Prove superior effectiveness

**Image 5 – Quality & Construction**
- Focus: Unique quality/material advantages identified in CSV analysis (NO review quotes or competitor comparison)
- Content: Premium features competitor lacks
- Purpose: Establish quality superiority

**Image 6 – Emotional Connection**
- Focus: Unique lifestyle/satisfaction advantages from CSV insights (NO review quotes or competitor comparison)
- Content: Emotional benefits competitor misses
- Purpose: Create desire and connection

**Image 7 – Comprehensive Comparison**
- Focus: Secondary advantages not covered in other images
- Content: Point-by-point comparison of remaining differentiators
- Purpose: Summarize all unique advantages
- **This is the ONLY image where 'Us vs Competitor' comparison and customer review quotes/content may be included.**

**Image 8 – Variant Explanation**
- Focus: Beginner-friendly, salesperson-like explanation of product variants (if {variants} provided)
- Content: Engaging, conversational descriptions of each variant, explaining what it is and scenarios where it's ideal, or "No variant details given"
- Purpose: Educate customers with zero knowledge about variant options in a friendly, sales-oriented tone
- **NO review quotes or competitor comparison.**

**Content Distribution Rules:**
1. Assign each unique competitor weakness or variant explanation to exactly ONE image
2. No content overlap between images
3. Each image must justify its existence with unique value
4. Progressive information architecture
5. Mobile-optimized, thumb-stopping design for each
6. Use comparison table, context analysis, and variant information for content
7. **NO review quotes or competitor comparison in Images 2–6 or 8. Only in Image 7.
8. Do not include the packaging details as a content in an image strictly**
""",
        agent=image_strategist,
        expected_output="""
Strategic content distribution plan with:
- 7 distinct image purposes with no content overlap
- Specific unique competitor weaknesses and salesperson-like variant explanations assigned to each image
- Progressive information architecture
- Mobile-first design considerations
- Zero repetition framework for maximum conversion
- Informed by comparison table, context analysis, and variant information
- **NO review quotes or competitor comparison in Images 2–6 or 8. Only in Image 7.**
""",
        output_file='{product_id}/3.amazon_image_strategy.txt'
    )

def create_finalize_amazon_image_specs_task():
    return Task(
        description="""
Create EXACT image generation prompts for 7 Amazon listing images for any product. Each prompt must be self-contained, complete, and designed to produce visually aesthetic Amazon-ready images like top-rated listings (e.g., YETI, d'Alba, luxury skincare). In addition to all existing requirements, every image prompt must use and emphasize these visual/aesthetic keywords:
- Photorealistic product render
- Bright, clean white background
- Soft shadows
- Minimalist composition
- Mobile-optimized layout
- Modern sans-serif font
- Natural lighting
- Professional studio style
- Lifestyle integration
- Elegant iconography
- Color-accented sections (e.g., gold tones, gentle creams, brand colors)
- High contrast for text readability
All text/content on the image must be short, nice, catchy, and visually attractive. Every word and visual element must serve a clear purpose and contribute to the image's appeal.

**VISUAL STYLE REQUIREMENTS:**
For all prompts, use the following keywords to guide image generation toward a premium, clean, mobile-optimized aesthetic:
- photorealistic product render
- clean white background with soft shadows
- minimalist composition with central focus
- mobile-optimized layout with large, bold, sans-serif fonts
- soft natural lighting, subtle gradients or glow when needed
- elegant, brand-colored icons or overlays
- lifestyle scenes with real people (if applicable) in modern, well-lit settings
- premium packaging or close-up texture shots (for quality)
- product-in-use moments with emotional facial expressions
- layout sections or comparison tables with good spacing and modern flow

**STRICT CONTENT RULES:**
- **Do NOT include any customer review quotes or content in Images 2–6 or 8.**
- **Do NOT include any 'Us vs Competitor' comparison in Images 2–6 or 8.**
- **All competitor comparison and review quotes must be strictly limited to Image 7.**

**Required Output Format for Each Image Prompt:**
🟩 **Image 2 – Primary Hero Advantage**
**Image Generation Prompt:**
Headline: [Bold headline for the product’s main benefit]
Subtext: [Supporting detail that enhances the hero message]
Visual: [Photorealistic product image with primary advantage depicted in action or symbolically]
Icons: [Relevant icons that match the benefit]
Design: Clean white background, soft shadows, centered layout, bold headline, mobile-friendly font, brand-colored accents
**NO review quotes or competitor comparison.**

🟩 **Image 3 – Usability Excellence**
**Image Generation Prompt:**
Headline: [Simple usability statement]
Steps: "1. [Step 1]", "2. [Step 2]", "3. [Step 3]"
Visual: [Step-by-step use case or hand-holding product with arrows/flow]
Icons: [Icons for each step—hand, droplet, glow, etc.]
Design: Minimal flow layout with arrows, white background, legible spacing for mobile
**NO review quotes or competitor comparison. The usabilty should not be common like unpacking, washing, drying, etc. It should be unique and specific to the product. Sometimes if you think users would know how to use the product, you can skip the steps and tell how it helps them. After using the product, you can tell how it helps them.**

🟩 **Image 4 – Performance Results**
**Image Generation Prompt:**
Headline: [Performance promise headline]
Benefits: "• [Result 1]", "• [Result 2]", "• [Result 3]"
Visual: [Before-after split, glowing effect, ingredient burst, or result-focused mockup]
Icons: [Icons showing strength, glow, hydration, etc.]
Design: High contrast split or highlight zones. Clean, modern layout with bold text.
**NO review quotes or competitor comparison.**

🟩 **Image 5 – Quality & Construction**
**Image Generation Prompt:**
Headline: [What makes it premium]
Visual: [Zoomed-in material/ingredient/texture shots with callouts]
Callouts: "[Feature 1]", "[Feature 2]", "[Feature 3]"
Icons: [Icons matching features—leaf, bottle, droplet, etc.]
Design: Premium color palette (e.g., gold, steel, matte), close-up visuals, modern mobile layout
**NO review quotes or competitor comparison.**

🟩 **Image 6 – Emotional Connection**
**Image Generation Prompt:**
Headline: [Emotive tagline]
Visual: [Real person using the product with a smile/confident look, in a relatable setting]
Emotional Text: [Feel-good benefit or lifestyle change]
Lifestyle Elements: [Setting like home, outdoors, travel, vanity]
Icons: [Emotion or lifestyle icons]
Design: Warm tones (peach, cream, gold), clean layout, natural lighting, mobile-friendly spacing
**NO review quotes or competitor comparison.**

🟩 **Image 7 – Comprehensive Comparison**
**Image Generation Prompt:**
Headline: [Why choose us]
Table: Columns: "Feature", "Us", "Other Products"
Rows: "[Feature 1]: Us ✅ [Advantage] | Other Products ❌ [Weakness]", "[Feature 2]: Us ✅ [Advantage] | Other Products ❌ [Weakness]", "[Feature 3]: Us ✅ [Advantage] | Other Products ❌ [Weakness]"
Icons: Green checkmarks, red X marks
Design: Clean bordered table layout with color distinction for rows, easy to scan on mobile
It should be unique and specific to that product.
**This is the ONLY image where 'Us vs Other Products' comparison and customer review quotes/content may be included.**

🟩 **Image 8 – Variant Explanation**
**Image Generation Prompt:**
Headline: [Pick your variant]
[If variants provided: Table with "Variant", "Description", "Best For". Visuals for each.]
[If no variants, strictly say no variants given]
Design: Friendly, color-coded visual rows, icons per variant, mobile-optimized and clean
**NO review quotes or competitor comparison.**

**FINAL OUTPUT INSTRUCTIONS:**
✅ Each prompt must be image-generation ready with full text content
✅ All visual and stylistic elements must be clearly described
✅ No repeated or recycled text between prompts
✅ All prompts must follow premium eCommerce standards
✅ Ensure mobile optimization in layout, font size, spacing, and visual clarity
✅ **NO review quotes or competitor comparison in Images 2–6 or 8. Only in Image 7.**
""",
        agent=creative_director,
        expected_output="""
7 complete image generation prompts with:
- All text content for image included
- Detailed visual instructions using photorealistic and mobile-optimized descriptions
- Premium aesthetic aligned with top Amazon listings
- Unique layout design cues per image
- Strict formatting with no overlap across prompts
- Every prompt uses the required visual/aesthetic keywords and keeps content short, nice, and visually attractive
- **NO review quotes or competitor comparison in Images 2–6 or 8. Only in Image 7.**
"""
    )

def create_image_content_quality_check_task():
    return Task(
        description="""
Review the generated image prompts for all 7 Amazon listing images and ensure the following requirements are strictly met:
1. Content is clean, neat, short, and catchy (including subtext).
2. Font color is subtle and readable (add as a design instruction if missing).
3. No user review quotes or content are included in any image.
4. Comparison is only present in Image 7 (Comprehensive Comparison).
5. No statistics or percentages are included in any image.
6. The word 'competitor' is not included in any image.
If any requirement is not met, correct the prompt so that it fully complies.
Output ONLY the final, quality-checked image prompts, with no extra commentary, issues, or suggestions.
""",
        agent=image_content_quality_checker,
        expected_output="""
[The final, quality-checked image prompts only. No extra commentary, issues, or suggestions.]
""",
        output_file='{product_id}/amazon_images_final.txt'
    )

def generate_amazon_images(product_name: str, product_id: str, your_csv_path: str, competitor_csv_path: str, variants: str, generate_actual_images: bool = False, openai_api_key: str = None):
    """Generate Amazon listing images using CSV review analysis"""
    # Create tasks
    analyze_task = create_analyze_csv_reviews_task()
    context_task = create_context_analysis_task()
    strategy_task = create_amazon_image_strategy_task()
    finalize_task = create_finalize_amazon_image_specs_task()
    quality_check_task = create_image_content_quality_check_task()

    # Create crew
    crew = Crew(
        agents=[review_analyst, context_analyst, image_strategist, creative_director, image_content_quality_checker],
        tasks=[analyze_task, context_task, strategy_task, finalize_task, quality_check_task],
        process=Process.sequential,
        verbose=True
    )

    # Prepare inputs
    inputs = {
        "product_name": product_name,
        "product_id": product_id,
        "your_csv_path": your_csv_path,
        "competitor_csv_path": competitor_csv_path,
        "variants": variants
    }

    # Execute AI analysis
    print("\n🤖 Starting AI analysis and image generation...")
    result = crew.kickoff(inputs=inputs)

    # Generate actual images if requested
    if generate_actual_images and IMAGE_GEN_AVAILABLE and openai_api_key:
        print("\n🎨 Generating actual images...")
        try:
            image_specs_path = f"{product_id}/amazon_images_final.txt"
            if os.path.exists(image_specs_path):
                parser = ImageContentParser(image_specs_path)
                content_list = parser.get_formatted_content_list()
                if content_list:
                    generator = HighQualityImageGenerator(openai_api_key)
                    generated_images = generator.generate_all_images(content_list)
                    if generated_images:
                        print(f"\n✅ Images successfully generated and saved to: {generator.output_dir}")
                        print(f"📂 Total images generated: {len(generated_images)}")
                    else:
                        print("❌ No images were generated!")
                else:
                    print("❌ No content found in image specifications file!")
            else:
                print(f"❌ Image specifications file not found: {image_specs_path}")
        except Exception as e:
            print(f"❌ Error generating actual images: {e}")
            import traceback
            traceback.print_exc()

    return result

def automated_scrape_and_analyze(product_name, my_product_id, competitor_product_id, variants="", generate_images=False, openai_api_key=None):
    """
    Fully automated function that:
    1. Scrapes positive reviews for your product
    2. Scrapes critical reviews for competitor product
    3. Runs the AI analysis to generate 7 unique Amazon images
    4. Optionally generates actual images using OpenAI
    """
    print("\n" + "="*80)
    print("🚀 STARTING FULLY AUTOMATED AMAZON IMAGE GENERATION")
    print("="*80)
    print(f"📦 Product: {product_name}")
    print(f"🆔 Your Product ID: {my_product_id}")
    print(f"🏪 Competitor Product ID: {competitor_product_id}")
    print(f"📋 Variants: {variants if variants else 'None provided'}")
    print(f"🎨 Generate Images: {'Yes' if generate_images else 'No'}")
    print("="*80)

    # Create save directory
    save_dir = f"amazon_data/{my_product_id}"
    os.makedirs(save_dir, exist_ok=True)
    print(f"📁 Save directory created: {save_dir}")

    # Step 1: Scrape reviews for both products
    print("\n" + "="*50)
    print("STEP 1: SCRAPING PRODUCT REVIEWS")
    print("="*50)
    reviews_scraper = AmazonReviewsScraper(headless=False)
    try:
        # Scrape your product's positive reviews
        print(f"\n🔍 Scraping positive reviews for your product: {my_product_id}")
        my_reviews = reviews_scraper.scrape_reviews(my_product_id, is_my_product=True, max_pages=10)
        if my_reviews:
            reviews_scraper.save_to_csv(my_reviews, my_product_id, is_my_product=True, save_dir=save_dir)
            your_csv_path = f"{save_dir}/my_product_positive_reviews_{my_product_id}.csv"
            print(f"✅ Your product reviews saved to: {your_csv_path}")
        else:
            print("❌ Failed to scrape your product reviews")
            return None

        # Scrape competitor's critical reviews
        print(f"\n🔍 Scraping critical reviews for competitor: {competitor_product_id}")
        competitor_reviews = reviews_scraper.scrape_reviews(competitor_product_id, is_my_product=False, max_pages=10)
        if competitor_reviews:
            reviews_scraper.save_to_csv(competitor_reviews, competitor_product_id, is_my_product=False, save_dir=save_dir)
            competitor_csv_path = f"{save_dir}/competitor_critical_reviews_{competitor_product_id}.csv"
            print(f"✅ Competitor reviews saved to: {competitor_csv_path}")
        else:
            print("❌ Failed to scrape competitor reviews")
            return None
    except Exception as e:
        print(f"❌ Error scraping reviews: {e}")
        return None
    finally:
        reviews_scraper.close_driver()

    # Step 2: Run the AI analysis to generate images
    print("\n" + "="*50)
    print("STEP 2: RUNNING AI ANALYSIS TO GENERATE IMAGES")
    print("="*50)

    # Verify all files exist
    files_to_check = [
        (your_csv_path, "Your product reviews CSV"),
        (competitor_csv_path, "Competitor reviews CSV")
    ]
    for file_path, file_desc in files_to_check:
        if not os.path.exists(file_path):
            print(f"❌ {file_desc} not found: {file_path}")
            return None
        else:
            print(f"✅ {file_desc} found: {file_path}")

    try:
        print("\n🤖 Starting AI analysis and image generation...")
        result = generate_amazon_images(
            product_name=product_name,
            product_id=my_product_id,
            your_csv_path=your_csv_path,
            competitor_csv_path=competitor_csv_path,
            variants=variants,
            generate_actual_images=generate_images,
            openai_api_key=openai_api_key
        )
        print("\n" + "=" * 80)
        print("🎨 SUCCESS! 7 UNIQUE AMAZON IMAGES GENERATED!")
        print("=" * 80)
        print(result)

        # Save the final result
        final_result_path = f"{save_dir}/amazon_images_final.txt"
        with open(final_result_path, 'w', encoding='utf-8') as f:
            f.write(str(result))
        print(f"\n💾 Final results saved to: {final_result_path}")
        return result
    except Exception as e:
        print(f"❌ Error during AI analysis: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """
    Main function - handles both scenarios:
    1. Only competitor product ID available
    2. Both your product ID and competitor product ID available
    """
    print("\n🎯 FULLY AUTOMATED AMAZON LISTING IMAGE GENERATOR")
    print("With Review Analysis + Optional Image Generation")
    print("=" * 90)
    print("✨ Just provide simple inputs and get 7 unique images!")
    print("✨ Everything else is completely automated - no more manual file paths!")
    print("=" * 90)

    # Get product name first
    print("\n📝 BASIC INFORMATION:")
    print("-" * 25)
    product_name = input("1. Enter your product name: ").strip()
    if not product_name:
        print("❌ Product name is required!")
        return

    # Ask about available product IDs
    print("\n📦 PRODUCT ID AVAILABILITY:")
    print("-" * 30)
    print("What product IDs do you have available?")
    print("1. Only competitor product ID (we'll use it for both analysis)")
    print("2. Both your product ID and competitor product ID")
    id_choice = input("\nEnter your choice (1 or 2): ").strip()

    my_product_id = None
    competitor_product_id = None
    if id_choice == "1":
        print("\n📝 COMPETITOR PRODUCT ID:")
        print("-" * 25)
        competitor_input = input("Enter competitor Amazon product ID: ").strip()
        if not competitor_input:
            print("❌ Competitor product ID is required!")
            return
        my_product_id = competitor_input
        competitor_product_id = competitor_input
        print(f"✅ Using {competitor_input} for both product analysis")
        print(" • Positive reviews will be analyzed from this product")
        print(" • Critical reviews will also be analyzed from this product")
    elif id_choice == "2":
        print("\n📝 PRODUCT IDs:")
        print("-" * 15)
        my_product_id = input("Enter your Amazon product ID (from URL): ").strip()
        if not my_product_id:
            print("❌ Your product ID is required!")
            return
        competitor_product_id = input("Enter competitor Amazon product ID: ").strip()
        if not competitor_product_id:
            print("❌ Competitor product ID is required!")
            return
        print(f"✅ Using separate products for analysis:")
        print(f" • Your product ({my_product_id}): Positive reviews")
        print(f" • Competitor ({competitor_product_id}): Critical reviews")
    else:
        print("❌ Invalid choice. Please select 1 or 2.")
        return

    print("\n📝 OPTIONAL INPUTS:")
    print("-" * 20)
    variants = input("Enter product variants (comma-separated, or press Enter to skip): ").strip()

    # Ask about image generation preference
    print("\n🎨 IMAGE GENERATION OPTIONS:")
    print("-" * 30)
    print("Choose what you want to generate:")
    print("1. Only image suggestions and prompts (fast, free)")
    print("2. Generate actual images using OpenAI DALL-E (requires API key, costs money)")
    choice = input("\nEnter your choice (1 or 2): ").strip()

    generate_images = False
    openai_api_key = None
    if choice == "2":
        if not IMAGE_GEN_AVAILABLE:
            print("❌ Image generation modules not available. Only image suggestions will be generated.")
        else:
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                generate_images = True
                print("✅ Actual images will be generated using OpenAI DALL-E")
            else:
                print("❌ No API key provided. Only image suggestions will be generated.")

    # Confirmation
    print("\n" + "="*60)
    print("📋 AUTOMATION SUMMARY")
    print("="*60)
    print(f"📦 Product: {product_name}")
    if id_choice == "1":
        print(f"🆔 Product ID (used for all analysis): {my_product_id}")
        print("📊 Analysis Mode: Single product analysis")
        print(" • Positive reviews from this product")
        print(" • Critical reviews from this product")
    else:
        print(f"🆔 Your Product ID: {my_product_id}")
        print(f"🏪 Competitor ID: {competitor_product_id}")
        print("📊 Analysis Mode: Dual product comparison")
        print(" • Positive reviews from your product")
        print(" • Critical reviews from competitor")
    print(f"📋 Variants: {variants if variants else 'None'}")
    print(f"🎨 Generate Images: {'Yes (OpenAI DALL-E)' if generate_images else 'No (suggestions only)'}")
    print("\n🤖 The system will automatically:")
    print(" ✅ Scrape and analyze product reviews")
    print(" ✅ Run AI analysis with multiple specialized agents")
    print(" ✅ Generate 7 unique Amazon image prompts")
    if generate_images:
        print(" ✅ Generate actual images using OpenAI DALL-E")
    print(" ✅ Save everything in organized folders")

    confirm = input("\n🚀 Start automated process? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Process cancelled.")
        return

    # Run the automated process
    try:
        result = automated_scrape_and_analyze(
            product_name,
            my_product_id,
            competitor_product_id,
            variants,
            generate_images,
            openai_api_key
        )
        if result:
            print("\n" + "🎉" * 20)
            print("🎉 AUTOMATION COMPLETED SUCCESSFULLY! 🎉")
            print("🎉" * 20)
            print(f"\n📁 All files saved in: amazon_data/{my_product_id}/")
            print("📋 Generated files:")
            print(f" • Your reviews: my_product_positive_reviews_{my_product_id}.csv")
            print(f" • Competitor reviews: competitor_critical_reviews_{competitor_product_id}.csv")
            print(f" • Analysis results: 1.comparison_table.txt")
            print(f" • Context analysis: 2.complains and why our product.txt")
            print(f" • Image strategy: 3.amazon_image_strategy.txt")
            print(f" • Final image prompts: amazon_images_final.txt")
            if generate_images:
                print(f" • Generated images: generated_images_*/")
            print("\n✨ Ready to use for your Amazon listing!")
        else:
            print("\n❌ Automation failed. Please check the error messages above.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()