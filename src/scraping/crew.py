import os
import datetime
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, FileWriterTool
from langchain_openai import ChatOpenAI
import yaml

@CrewBase
class ProductScraperCrew():
    """ProductScraperCrew crew"""
    
    # Set config file paths as class attributes
    agents_config = 'D:\\college\\Profit_Story\\scraping\\scraping\\src\\scraping\\config\\agents.yaml'
    tasks_config = 'D:\\college\\Profit_Story\\scraping\\scraping\\src\\scraping\\config\\tasks.yaml'

    def __init__(self, website_url=None):
        # Set default URL if none provided
        self.website_url = website_url or "https://www.amazon.in/Brightening-Formulated-Extract-Brightens-Suitable/dp/B0BLCM1BQD"
        
        # Initialize tools
        self.scrape_tool = ScrapeWebsiteTool(website_url=self.website_url)
        self.file_writer_tool = FileWriterTool()
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        
        # Create output directory if it doesn't exist
        self.output_dir = 'output-files'
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load configuration files
        self.agents_data = self._load_config(self.agents_config)
        self.tasks_data = self._load_config(self.tasks_config)
        
        # Call parent constructor
        super().__init__()
    
    def _load_config(self, config_path):
        """Helper method to load YAML configuration files"""
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            print(f"Error loading {config_path}: {str(e)}")
            raise
    
    def update_website_url(self, url):
        """Update the website URL and reinitialize the scrape tool"""
        self.website_url = url
        self.scrape_tool = ScrapeWebsiteTool(website_url=self.website_url)
    
    @agent
    def scraper(self) -> Agent:
        print("Initializing scraper")
        
        return Agent(
            role=self.agents_data['scraper']['role'].format(link=self.website_url),
            goal=self.agents_data['scraper']['goal'].format(link=self.website_url),
            backstory=self.agents_data['scraper']['backstory'].format(link=self.website_url),
            tools=[self.scrape_tool, self.file_writer_tool],
            llm=self.llm,
            verbose=True
        )
    
    @task
    def scraping_task(self) -> Task:
        print("Starting scraping_task")
        
        # Generate timestamp for unique file name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{self.output_dir}/customer_reviews_{timestamp}.csv"
        
        return Task(
            description=self.tasks_data['scraping_task']['description'].format(link=self.website_url),
            expected_output=self.tasks_data['scraping_task']['expected_output'],
            agent=self.scraper(),
            output_file=output_file
        )
    
    @crew
    def crew(self) -> Crew:
        """Creates the ProductScraperCrew crew"""
        print("Creating ProductScraperCrew crew")
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )