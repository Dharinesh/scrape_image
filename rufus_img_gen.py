#rufus.py - Fully Automated Version with Image Generation Integration
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from typing import Type, Optional
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
import json
import os
import time

# Import the scraping classes from combined.py
from combined import AmazonRufusScraper, AmazonReviewsScraper

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

class RufusInsightsInput(BaseModel):
    """Input schema for Rufus questions and insights analysis"""
    insights_path: str = Field(..., description="Path to the text file containing Rufus questions and customer insights")
    
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
            
            # Get basic info
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
                    
                    # Get samples by rating if available
                    rating_cols = [col for col in columns if any(term in col.lower() for term in ['rating', 'star', 'score'])]
                    if rating_cols:
                        rating_col = rating_cols[0]
                        review_samples = {}
                        for rating in sorted(df[rating_col].unique()):
                            # Ensure we are working with a pandas Series, not numpy array
                            samples_series = df[df[rating_col] == rating][text_col]
                            # Convert to pandas Series if it's a numpy array
                            if isinstance(samples_series, np.ndarray):
                                samples_series = pd.Series(samples_series)
                            samples = pd.Series(samples_series).dropna().head(3).tolist()
                            review_samples[f"{rating}_star"] = samples
                        analysis_results["review_samples"] = review_samples
                    else:
                        # Just get random samples
                        analysis_results["review_samples"] = {
                            "random_samples": df[text_col].dropna().head(10).tolist()
                        }
            
            # Keyword analysis
            if "keyword" in query_lower or "search" in query_lower:
                # Extract keywords from query
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
    role='Comprehensive CSV Review Analyst with Rufus Integration',
    goal='Analyze positive and critical reviews from CSV files while ensuring all Rufus questions are addressed and customer insights are incorporated into the comparison table, focusing only on high-helpful-vote reviews and delivering a differentiated 2-column table.',
    backstory="""You are an expert at analyzing comprehensive customer review data from CSV files while integrating Rufus questions and customer insights. 
    You excel at processing large volumes of reviews, prioritizing those with high helpful votes, and ensuring that every Rufus question is addressed in your analysis.
    
    Your specialties include:
    - Extracting only meaningful, specific complaints from other product critical reviews that are unique to their product/brand
    - Ensuring every Rufus question from the insights file is answered in the comparison table
    - Incorporating customer insights from the insights file (but NO statistics or quotes for image use)
    - From your product's positive reviews, surfacing real-world advantages that directly address Rufus questions
    - Excluding generic feedback while ensuring Rufus concerns are specifically addressed
    - Delivering a 2-column table that answers customer questions without including statistics or quotes
    
    You use CSV analysis and Rufus insights to create a comprehensive comparison that addresses real customer questions and concerns.""",
    verbose=True,
    allow_delegation=False,
    tools=[csv_analyzer]
)

context_analyst = Agent(
    role='Contextual Analysis Expert with Customer Insights Integration',
    goal='Generate clear, non-repetitive context for product strengths and other product weaknesses based on review analysis and Rufus customer insights, without including statistics or quotes',
    backstory="""You are a contextual analysis expert who synthesizes comprehensive review data with Rufus questions and customer insights into clear, 
    actionable content. Your focus is on creating unique, non-repetitive content that highlights your product's 
    strengths and other product weaknesses while specifically addressing customer questions.
    
    IMPORTANT: You never include statistics, percentages, ratings, or customer quotes in your analysis as this content will be used for images.""",
    verbose=True,
    allow_delegation=False,
    tools=[]
)

image_strategist = Agent(
    role='Visual Marketing Strategist with Customer Question Integration',
    goal='Create non-repetitive, strategic visual specifications for high-conversion Amazon listing images based on unique other product weaknesses, Rufus questions, and customer insights, strictly avoiding statistics and quotes',
    backstory="""You are a visual marketing expert who transforms unique other product pain points, Rufus questions, and customer insights into 
    compelling, conversion-focused Amazon listing images with ZERO content repetition. You specialize in 
    strategically distributing unique selling points that directly answer customer questions and address their specific concerns.
    
    CRITICAL RESTRICTIONS:
    - NEVER include statistics, percentages, ratings, or numbers in image content
    - NEVER include customer quotes or testimonials in image specifications
    - NEVER use the word "competitor" in any image prompt
    - Use "other products" or "alternatives" instead of "competitor"
    
    You understand that customers ask specific questions (Rufus questions) and have particular concerns, so each image must strategically address these while building upon previous images with completely new information.""",
    verbose=True,
    allow_delegation=False,
    tools=[]
)

creative_director = Agent(
    role='Creative Director & Content Distribution Specialist with Customer Focus',
    goal='Create 7 unique Amazon listing images with zero repetition, ensuring Rufus questions are answered and customer insights are visually represented, while strictly avoiding statistics, quotes, and the word "competitor"',
    backstory="""You are a creative director who specializes in content distribution strategy for Amazon 
    listings while ensuring customer questions are answered and insights are incorporated. Your expertise is ensuring ZERO repetition across all images while making sure every important customer question gets addressed visually.
    
    CRITICAL CONTENT RESTRICTIONS:
    - NEVER include statistics, percentages, ratings, or numerical data in image prompts
    - NEVER include customer quotes, reviews, or testimonials in image specifications
    - NEVER use the word "competitor" - use "other products", "alternatives", or "other brands" instead
    - Focus on product benefits and features rather than comparative statistics
    
    You create a content hierarchy where each image builds upon the previous one with completely new information, while strategically answering customer questions through compelling visual storytelling.
    
    You always use premium visual and stylistic keywords while ensuring customer concerns are addressed through compelling visual storytelling.""",
    verbose=True,
    allow_delegation=False,
    tools=[]
)

# Add Image Content Quality Checker Agent
image_content_quality_checker = Agent(
    role='Image Content Quality Checker with Customer Question Validation',
    goal='Ensure all Amazon image prompts are clean, neat, short, catchy, visually clear, follow all content rules, address key customer questions, and strictly exclude statistics, quotes, and the word "competitor"',
    backstory="""You are a meticulous Amazon image content quality checker with a focus on customer question coverage and content restrictions. Your job is to review all generated image prompts and ensure they:
    1. Are clean, neat, short, and catchy (including subtext)
    2. Have subtle and readable font color instructions
    3. Address key customer questions and concerns
    4. Follow all content rules (no inappropriate comparisons, etc.)
    5. Maintain visual appeal while being informative
    
    CRITICAL CONTENT RESTRICTIONS YOU MUST ENFORCE:
    - Remove ANY statistics, percentages, ratings, or numerical data from image prompts
    - Remove ANY customer quotes, reviews, or testimonials from image specifications
    - Replace the word "competitor" with "other products", "alternatives", or "other brands"
    - Ensure focus remains on product benefits rather than comparative data
    
    You are especially focused on ensuring customer questions are answered while maintaining clean, professional image content without restricted elements.""",
    verbose=True,
    allow_delegation=False,
    tools=[]
)

# Define Tasks
def create_analyze_csv_reviews_with_rufus_task():
    return Task(
        description="""
        Comprehensively analyze ALL reviews from both CSV files for {product_name}, while integrating Rufus questions and customer insights, focusing ONLY on reviews with helpful votes and ensuring every Rufus question is addressed.
        
        **CRITICAL CONTENT RESTRICTIONS:**
        - DO NOT include any statistics, percentages, ratings, or numerical data in the final comparison table
        - DO NOT include any customer quotes or testimonials in the comparison table
        - Focus on product features, benefits, and capabilities rather than statistical data
        - Use "other products" or "alternatives" instead of "competitor"
        
        **Step 1: Analyze Rufus Questions & Customer Insights**
        Use rufus_insights_analyzer to extract and analyze all Rufus questions and customer insights from {rufus_insights_path}.
        Identify:
        - All customer questions that need to be answered
        - Key concerns and satisfaction points (without including quotes)
        - Specific insights about the product (conceptual, not statistical)
        
        **Step 2: Analyze YOUR product positive reviews CSV**
        Use csv_analyzer to extract and analyze ALL positive review data from your product CSV at {your_csv_path}, but only include reviews with helpful votes.
        Look for answers to Rufus questions and evidence supporting customer insights.
        
        **Step 3: Analyze OTHER PRODUCT critical reviews CSV**
        Use csv_analyzer to extract and analyze ALL critical review data from other product CSV at {competitor_csv_path}, but only include reviews with helpful votes.
        Look for complaints that validate Rufus questions and customer concerns.
        
        **Step 4: Create Rufus-Integrated Comparison (NO STATS/QUOTES)**
        - Ensure EVERY Rufus question is addressed in the comparison table
        - From other product's critical reviews, identify complaints that:
            • Directly relate to Rufus questions
            • Validate customer concerns from insights
            • Are specific to the other product
            • Reflect real, contextual pain points (described conceptually, not with statistics)
        - From your product's positive reviews, identify advantages that:
            • Answer Rufus questions directly
            • Address specific customer concerns
            • Demonstrate real-world effectiveness (described in benefits, not numbers)
        
        **Step 5: Enhanced Deliverable Table (CONTENT CLEAN)**
        - Deliver output in a 2-column table: 'Customer Question/Concern (from Rufus & Reviews)' | 'How Our Product Addresses This'
        - Each row should address a specific customer question or validated concern
        - NO statistics, percentages, ratings, or numerical data
        - NO customer quotes or testimonials
        - Use "other products" instead of "competitor"
        - Focus on features, benefits, and capabilities
        
        **Step 6: Validation Check**
        - Verify every Rufus question has been addressed
        - Confirm NO statistics or quotes are included
        - Ensure customer insights are reflected conceptually in the comparison
        
        **Step 7: Save and summarize**
        - Save the enhanced table to '{product_id}/1.rufus_integrated_comparison_table.txt'
        - Summarize how many Rufus questions were addressed
        """,
        agent=review_analyst,
        expected_output="""
        - Enhanced 2-column table: 'Customer Question/Concern (from Rufus & Reviews)' | 'How Our Product Addresses This'
        - Every Rufus question addressed in the comparison
        - NO statistics, percentages, ratings, or numerical data included
        - NO customer quotes or testimonials included
        - Use "other products" instead of "competitor"
        - Focus on high helpful vote reviews
        - Table saved to '{product_id}/1.rufus_integrated_comparison_table.txt'
        - Summary of Rufus question coverage
        """,
        tools=[csv_analyzer],
        output_file='{product_id}/1.rufus_integrated_comparison_table.txt'
    )

def create_context_analysis_with_rufus_task():
    return Task(
        description="""
        Based on the dual CSV review analysis and Rufus insights integration, generate context for {product_name} under the following headings:
        - Why our product?
        - What questions do customers have? (from Rufus analysis)
        - How our product answers customer questions?
        - What complaints they have on other products?
        - How our product solves the other product problem?
        
        **CRITICAL CONTENT RESTRICTIONS:**
        - DO NOT include any statistics, percentages, ratings, or numerical data
        - DO NOT include any customer quotes or testimonials
        - Use "other products" or "alternatives" instead of "competitor"
        - Focus on product features, benefits, and capabilities rather than statistical comparisons
        
        **Instructions:**
        - Use the Rufus-integrated comparison table and customer insights
        - Ensure every Rufus question is addressed in the context
        - Prioritize insights from high helpful vote reviews
        - Include variant-specific feedback with practical use cases if {variants} is provided
        - Provide specific examples from CSV data (conceptual benefits, not statistics)
        - Ensure no content overlaps with image specifications
        - Save output to '{product_id}/2.rufus_integrated_context.txt'
        
        **Output Format:**
        # Why Our Product?
        [Detailed reasons based on your product's strengths, incorporating customer insights from Rufus analysis without statistics]
        
        # What Questions Do Customers Have?
        [List and explain all Rufus questions and common customer concerns identified]
        
        # How Our Product Answers Customer Questions
        [Clear explanations of how your product addresses each customer question, backed by review insights but no statistics]
        
        # What Complaints They Have on Other Products?
        [Specific other product weaknesses that relate to customer questions and concerns, no statistics]
        
        # How Our Product Solves the Other Product Problem?
        [Clear explanations with benefits and features supporting your advantages, no statistics]
        """,
        agent=context_analyst,
        expected_output="""Enhanced context analysis with:
        - All Rufus questions addressed
        - Clear answers to customer concerns
        - Other product weaknesses tied to customer questions
        - Solutions backed by product benefits and features (no statistics)
        - NO customer quotes or testimonials
        - Use "other products" instead of "competitor"
        - Variant-specific insights if provided
        - Saved to '{product_id}/2.rufus_integrated_context.txt'
        - No overlap with image content""",
        output_file='{product_id}/2.rufus_integrated_context.txt'
    )

def create_amazon_image_strategy_with_rufus_task():
    return Task(
        description="""
        Based on the dual CSV review analysis, Rufus insights integration, and context analysis, create a strategic content distribution plan for 7 Amazon listing images that addresses customer questions and concerns through visual solutions.
        
        **CRITICAL CONTENT RESTRICTIONS FOR ALL IMAGES:**
        - NEVER include statistics, percentages, ratings, or numerical data in any image content
        - NEVER include customer quotes, testimonials, or review text in image specifications
        - NEVER use the word "competitor" - use "other products", "alternatives", or "other brands"
        - Focus on product benefits, features, and capabilities rather than comparative statistics
        
        **CRITICAL CUSTOMER SOLUTION INTEGRATION:**
        - Each image must implicitly address customer concerns through visual solutions
        - Show answers to customer questions without explicitly stating the questions
        - Ensure customer concerns are resolved through product benefits shown visually
        - People should understand the solutions just by looking at the images
        
        **ENHANCED STRATEGIC IMAGE DISTRIBUTION FRAMEWORK:**
        
        **Image 2 – Primary Customer Concern Solution** 
        - Focus: Address the main customer concern through primary product benefit
        - Content: Clear visual solution to main customer pain point (NO EXPLICIT QUESTIONS)
        - Purpose: Immediately show solution to top customer concern
        
        **Image 3 – Usability & Customer Experience**
        - Focus: Demonstrate superior usability and ease-of-use through visual flow
        - Content: Visual demonstration of effortless user experience 
        - Purpose: Show how product provides seamless experience
        
        **Image 4 – Performance & Results**
        - Focus: Showcase performance capabilities through visual results
        - Content: Results demonstration that proves effectiveness through features
        - Purpose: Prove superior results through product design
        
        **Image 5 – Quality & Reliability**
        - Focus: Display quality features and durability through visual proof
        - Content: Quality demonstration that shows reliability through construction
        - Purpose: Establish quality superiority through visual product attributes
        
        **Image 6 – Customer Satisfaction & Lifestyle**
        - Focus: Show lifestyle enhancement and satisfaction through product benefits
        - Content: Emotional benefits that demonstrate lifestyle improvement
        - Purpose: Connect with customer needs through visual product advantages
        
        **Image 7 – Comprehensive Feature Comparison**
        - Focus: Show all advantages in comparison format through features
        - Content: Feature-based comparison showing superiority through benefits
        - Purpose: Complete advantage coverage through visual feature comparison
        
        **Image 8 – Variant Selection Guide (Benefit-Based)**
        - Focus: Guide variant selection through benefit demonstration
        - Content: Clear guidance showing which variant provides which benefits
        - Purpose: Help customers choose based on visual benefit demonstration
        
        **Customer Solution Integration Rules:**
        1. Every customer concern must be addressed through visual solutions across the 7 images
        2. NO explicit questions or Q&A format in any image
        3. Visual elements should demonstrate solutions through product benefits
        4. People should understand answers just by looking at the images
        5. Progressive confidence building through visual benefit demonstration
        """,
        agent=image_strategist,
        expected_output="""Solution-focused strategic content distribution plan with:
        - 7 distinct image purposes addressing customer concerns through solutions
        - Every customer concern resolved through visual benefits
        - NO explicit question-answer format
        - Customer concerns visually addressed through product benefits
        - Progressive solution-demonstration architecture
        - Zero repetition while ensuring comprehensive solution coverage
        """,
        output_file='{product_id}/3.rufus_integrated_image_strategy.txt'
    )

def create_finalize_amazon_image_specs_with_rufus_task():
    return Task(
        description="""
        Create EXACT image generation prompts for 7 Amazon listing images that address customer questions and incorporate customer insights.
        
        **CRITICAL CONTENT RESTRICTIONS FOR ALL IMAGES:**
        - NEVER include statistics, percentages, ratings, or numerical data
        - NEVER include customer quotes, testimonials, or review excerpts
        - NEVER use the word "competitor" - use "other products", "alternatives", or "other brands"
        - Focus on product features, benefits, and capabilities
        
        **CUSTOMER QUESTION INTEGRATION REQUIREMENTS:**
        - Each image must implicitly address specific customer questions through visual benefits
        - Show solutions to customer concerns without explicitly stating the questions
        - Visual elements must demonstrate answers through product features and benefits
        - People should understand the answers just by looking at the image
        
        **Enhanced Output Format (Solution-Focused, Clean Content):**

        🟩 **Image 2 – Primary Customer Concern Solution**
        **Image Generation Prompt:**
        Headline: [Direct solution statement addressing top customer concern - no statistics]
        Key Solution: [Clear, confident product benefit that solves the main concern]
        Visual: [Product demonstrating the solution in action]
        Benefits: [Key product advantages that address the concern - no numbers]
        Design: Clean, solution-focused layout with clear benefit prominence
        
        🟩 **Image 3 – Usability & Customer Experience**
        **Image Generation Prompt:**
        Headline: [Ease of use statement]
        Simple Process: "1. [Step], 2. [Step], 3. [Result]"
        Visual: [Easy-to-follow demonstration showing effortless use]
        Icons: [User-friendly icons that support ease of use]
        Design: Customer-centric flow showing seamless experience
        
        🟩 **Image 4 – Performance & Results**
        **Image Generation Prompt:**
        Headline: [Performance promise that demonstrates effectiveness]
        Proven Results: 
        "• [Feature 1 that delivers results]"
        "• [Feature 2 that delivers results]" 
        "• [Capability 3 showing superior performance]"
        Visual: [Before-after or results demonstration]
        Design: Results-focused layout with product capability emphasis
        
        🟩 **Image 5 – Quality & Reliability**
        **Image Generation Prompt:**
        Headline: [Quality assurance statement showing durability]
        Quality Promise: [Specific quality features that ensure reliability]
        Visual: [Close-up quality demonstration or construction details]
        Quality Features: [Relevant product attributes about build quality]
        Design: Premium, trust-building layout with quality emphasis
        
        🟩 **Image 6 – Customer Satisfaction & Lifestyle**
        **Image Generation Prompt:**
        Headline: [Satisfaction statement showing lifestyle enhancement]
        Lifestyle Benefits: [How product enhances daily life and satisfaction]
        Visual: [Happy customer using product in lifestyle context]
        Lifestyle Enhancement: [How product seamlessly fits into customer's life]
        Design: Warm, satisfaction-focused with customer happiness emphasis
        
        🟩 **Image 7 – Comprehensive Feature Comparison**
        **Image Generation Prompt:**
        Headline: [Complete advantage overview]
        Feature Comparison:
        "✅ [Our Advantage 1] vs Other Products: [Their Limitation]"
        "✅ [Our Advantage 2] vs Other Products: [Their Limitation]"
        "✅ [Our Advantage 3] vs Other Products: [Their Limitation]"
        Visual: [Clean feature comparison layout]
        Design: Advantage-focused comparison with clear superiority emphasis
        
        🟩 **Image 8 – Variant Selection Guide (Benefit-Based)**
        **Image Generation Prompt:**
        Headline: [Find your perfect match]
        Variant Guide: 
        "[Variant 1]: Perfect for [specific benefit/use case]"
        "[Variant 2]: Ideal for [specific benefit/use case]"
        "[Variant 3]: Best for [specific benefit/use case]"
        Visual: [Clear variant comparison with customer use cases]
        Design: Decision-making focused layout helping customer choice
        
        **FINAL SOLUTION-FOCUSED REQUIREMENTS:**
        ✅ Every image implicitly addresses customer questions through solutions
        ✅ NO explicit question-answer format in any image
        ✅ Visual elements demonstrate answers through product benefits
        ✅ People understand solutions just by looking at the image
        ✅ All premium aesthetic standards maintained
        """,
        agent=creative_director,
        expected_output="""
        7 complete solution-focused image generation prompts with:
        - Implicit customer question addressing through visual benefits
        - NO explicit question-answer format
        - Visual elements demonstrating answers through product features
        - Solution-focused messaging that answers concerns without stating them
        - Premium aesthetic with benefit-centric messaging
        - Clear solutions to all customer concerns across the image set
        """
    )
    
def create_image_content_quality_check_with_rufus_task():
    return Task(
        description="""
        Review the generated image prompts for all 7 Amazon listing images and ensure they meet quality standards while properly addressing customer questions:
        
        **Quality Standards:**
        1. Content is clean, neat, short, and catchy (including subtext)
        2. Font color is subtle and readable (add as design instruction if missing)
        3. Customer questions are clearly addressed in appropriate images
        4. Customer metrics are included where relevant and accurate
        5. No inappropriate statistics or false claims
        6. Visual elements support customer concern resolution
        7. Progressive customer confidence building across images
        8. All Rufus questions are covered across the image set
        
        **Customer Question Validation:**
        - Verify that each image addresses specific customer concerns
        - Ensure customer metrics are accurately represented
        - Confirm that answers to customer questions are clear and compelling
        - Check that visual elements support customer concern resolution
        
        If any requirement is not met, correct the prompt to ensure full compliance with both quality and customer question standards.
        Output ONLY the final, quality-checked image prompts with proper customer question integration.
        """,
        agent=image_content_quality_checker,
        expected_output="""
        [Final, quality-checked image prompts with proper customer question integration. No extra commentary, issues, or suggestions.]
        """,
        output_file='{product_id}/amazon_images_final.txt'
    )

def generate_amazon_images_with_rufus(product_name: str, product_id: str, your_csv_path: str, competitor_csv_path: str, rufus_insights_path: str, variants: str, generate_actual_images: bool = False, openai_api_key: str = None):
    """Generate Amazon listing images using CSV analysis integrated with Rufus questions"""
    
    # Create tasks
    analyze_task = create_analyze_csv_reviews_with_rufus_task()
    context_task = create_context_analysis_with_rufus_task()
    strategy_task = create_amazon_image_strategy_with_rufus_task()
    finalize_task = create_finalize_amazon_image_specs_with_rufus_task()
    quality_check_task = create_image_content_quality_check_with_rufus_task()
    
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
            # Path to the generated image specifications
            image_specs_path = f"{product_id}/amazon_images_final.txt"
            
            if os.path.exists(image_specs_path):
                # Parse content from file
                parser = ImageContentParser(image_specs_path)
                content_list = parser.get_formatted_content_list()
                
                if content_list:
                    # Generate high-quality images
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


# --- Fully Automated Scraping and Analysis Integration ---
def automated_scrape_and_analyze(product_name, my_product_id, competitor_product_id, variants="", generate_images=False, openai_api_key=None):
    """
    Fully automated function that:
    1. Scrapes Rufus questions & customer insights
    2. Scrapes positive reviews for your product
    3. Scrapes critical reviews for competitor product
    4. Runs the AI analysis to generate 7 unique Amazon images
    5. Optionally generates actual images using OpenAI
    
    Only requires: product_name, my_product_id, competitor_product_id, variants (optional)
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
    
    # Step 1: Scrape Rufus questions & customer insights
    print("\n" + "="*50)
    print("STEP 1: SCRAPING RUFUS QUESTIONS & CUSTOMER INSIGHTS")
    print("="*50)
    
    product_url = f"https://www.amazon.in/dp/{my_product_id}"
    rufus_scraper = AmazonRufusScraper(headless=False)
    
    try:
        rufus_results = rufus_scraper.scrape_product_data(product_url)
        if rufus_results['success']:
            rufus_txt_path = rufus_scraper.save_to_txt(rufus_results, my_product_id, save_dir)
            print(f"✅ Rufus data saved to: {rufus_txt_path}")
        else:
            print("❌ Failed to scrape Rufus data")
            return None
    except Exception as e:
        print(f"❌ Error scraping Rufus data: {e}")
        return None
    finally:
        rufus_scraper.close()
    
    # Step 2: Scrape reviews for both products
    print("\n" + "="*50)
    print("STEP 2: SCRAPING PRODUCT REVIEWS")
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
    
    # Step 3: Run the AI analysis to generate images
    print("\n" + "="*50)
    print("STEP 3: RUNNING AI ANALYSIS TO GENERATE IMAGES")
    print("="*50)
    
    # Set file paths
    rufus_insights_path = f"{save_dir}/amazon_complete_data_{my_product_id}.txt"
    
    # Verify all files exist
    files_to_check = [
        (rufus_insights_path, "Rufus insights file"),
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
        result = generate_amazon_images_with_rufus(
            product_name=product_name,
            product_id=my_product_id,
            your_csv_path=your_csv_path,
            competitor_csv_path=competitor_csv_path,
            rufus_insights_path=rufus_insights_path,
            variants=variants,
            generate_actual_images=generate_images,
            openai_api_key=openai_api_key
        )
        
        print("\n" + "=" * 80)
        print("🎨 SUCCESS! 7 UNIQUE CUSTOMER-FOCUSED AMAZON IMAGES GENERATED!")
        print("=" * 80)
        print(result)
        
        # Save the final result
        final_result_path = f"{save_dir}/amazon_images_rufus_integrated_final.txt"
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
    print("With Rufus Questions + Customer Insights + Review Analysis + Optional Image Generation")
    print("=" * 90)
    print("✨ Just provide simple inputs and get 7 unique, customer-focused images!")
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
        
        # Use competitor ID for both positions
        my_product_id = competitor_input
        competitor_product_id = competitor_input
        
        print(f"✅ Using {competitor_input} for both product analysis")
        print("   • Rufus questions will be scraped from this product")
        print("   • Positive reviews will be analyzed from this product")
        print("   • Critical reviews will also be analyzed from this product")
        
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
        print(f"   • Your product ({my_product_id}): Rufus questions + positive reviews")
        print(f"   • Competitor ({competitor_product_id}): Critical reviews")
        
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
            openai_api_key = input("\n🔑 Enter your OpenAI API key: ").strip()
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
        print("   • Rufus questions from this product")
        print("   • Positive reviews from this product")
        print("   • Critical reviews from this product")
    else:
        print(f"🆔 Your Product ID: {my_product_id}")
        print(f"🏪 Competitor ID: {competitor_product_id}")
        print("📊 Analysis Mode: Dual product comparison")
        print("   • Rufus questions from your product")
        print("   • Positive reviews from your product")
        print("   • Critical reviews from competitor")
    
    print(f"📋 Variants: {variants if variants else 'None'}")
    print(f"🎨 Generate Images: {'Yes (OpenAI DALL-E)' if generate_images else 'No (suggestions only)'}")
    
    print("\n🤖 The system will automatically:")
    print("   ✅ Scrape Rufus questions and customer insights")
    print("   ✅ Scrape and analyze product reviews")
    print("   ✅ Run AI analysis with multiple specialized agents")
    print("   ✅ Generate 7 unique, customer-focused Amazon image prompts")
    if generate_images:
        print("   ✅ Generate actual images using OpenAI DALL-E")
    print("   ✅ Save everything in organized folders")
    
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
            print(f"   • Rufus insights: amazon_complete_data_{my_product_id}.txt")
            print(f"   • Your reviews: my_product_positive_reviews_{my_product_id}.csv")
            print(f"   • Competitor reviews: competitor_critical_reviews_{competitor_product_id}.csv")
            print(f"   • Analysis results: 1.rufus_integrated_comparison_table.txt")
            print(f"   • Context analysis: 2.rufus_integrated_context.txt")
            print(f"   • Image strategy: 3.rufus_integrated_image_strategy.txt")
            print(f"   • Final image prompts: amazon_images_final.txt")
            if generate_images:
                print(f"   • Generated images: generated_images_*/")
            print("\n✨ Ready to use for your Amazon listing!")
        else:
            print("\n❌ Automation failed. Please check the error messages above.")
            
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        
if __name__ == "__main__":
    main()