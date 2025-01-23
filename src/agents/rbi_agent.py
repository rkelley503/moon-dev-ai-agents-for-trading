"""
🌙 Moon Dev's RBI Agent (Research-Backtest-Implement)
Built with love by Moon Dev 🚀

Required Setup:
1. Create folder structure:
   src/
   ├── data/
   │   └── rbi/
   │       ├── research/         # Strategy research outputs
   │       ├── backtests/        # Initial backtest code
   │       ├── backtests_final/  # Debugged backtest code
   │       ├── BTC-USD-15m.csv  # Price data for backtesting
   │       └── ideas.txt        # Trading ideas to process

2. Environment Variables:
   - DEEPSEEK_KEY: Your DeepSeek API key

3. Create ideas.txt:
   - One trading idea per line
   - Can be YouTube URLs, PDF links, or text descriptions
   - Lines starting with # are ignored

This agent automates the RBI process:
1. Research: Analyzes trading strategies from various sources
2. Backtest: Creates backtests for promising strategies
3. Debug: Fixes technical issues in generated backtests

Remember: Past performance doesn't guarantee future results!
"""

# DeepSeek Model Selection per Agent
# Options for each: "deepseek-chat" (faster) or "deepseek-reasoner" (more analytical)
RESEARCH_MODEL = "deepseek-chat"  # Analyzes strategies thoroughly
BACKTEST_MODEL = "deepseek-chat"      # Creative in implementing strategies
DEBUG_MODEL = "deepseek-chat"     # Careful code analysis

# Agent Prompts

RESEARCH_PROMPT = """
You are Moon Dev's Research AI 🌙
Analyze the trading strategy content and create detailed instructions.
Focus on:
1. Key strategy components
2. Entry/exit rules
3. Risk management
4. Required indicators

Output ONLY the strategy instructions for backtesting.
Be precise and detailed, as another AI will use these instructions to create a backtest.
"""

BACKTEST_PROMPT = """
You are Moon Dev's Backtest AI 🌙
Create a backtesting.py implementation for the strategy.
Include:
1. All necessary imports
2. Strategy class with indicators
3. Entry/exit logic
4. Risk management
5. Parameter optimization
6. your size should be 1,000,000
7. If you need indicators use TA lib or pandas TA. Do not use backtesting.py's indicators. 

IMPORTANT DATA HANDLING:
1. Clean column names by removing spaces: data.columns = data.columns.str.strip().str.lower()
2. Drop any unnamed columns: data = data.drop(columns=[col for col in data.columns if 'unnamed' in col.lower()])
3. Ensure proper column mapping to match backtesting requirements:
   - Required columns: 'Open', 'High', 'Low', 'Close', 'Volume'
   - Use proper case (capital first letter)
4. When optimizing parameters:
   - Never try to optimize lists directly
   - Break down list parameters (like Fibonacci levels) into individual parameters
   - Use ranges for optimization (e.g., fib_level_1=range(30, 40, 2))


INDICATOR CALCULATION RULES:
1. ALWAYS use self.I() wrapper for ANY indicator calculations
2. Use talib functions instead of pandas operations:
   - Instead of: self.data.Close.rolling(20).mean()
   - Use: self.I(talib.SMA, self.data.Close, timeperiod=20)
3. For swing high/lows use talib.MAX/MIN:
   - Instead of: self.data.High.rolling(window=20).max()
   - Use: self.I(talib.MAX, self.data.High, timeperiod=20)

BACKTEST EXECUTION ORDER:
1. Run initial backtest with default parameters first
2. Print full stats using print(stats) and print(stats._strategy)
3. Show initial performance plot
4. Then run optimization
5. Show optimized results and final plot

RISK MANAGEMENT:
1. Always calculate position sizes based on risk percentage
2. Use proper stop loss and take profit calculations
3. Include risk-reward ratio in optimization parameters
4. Print entry/exit signals with Moon Dev themed messages

If you need indicators use TA lib or pandas TA. Do not use backtesting.py's indicators. 

Use this data path: /Users/md/Dropbox/dev/github/moon-dev-ai-agents-for-trading/src/data/rbi/BTC-USD-15m.csv
the above data head looks like below
datetime, open, high, low, close, volume,
2023-01-01 00:00:00, 16531.83, 16532.69, 16509.11, 16510.82, 231.05338022,
2023-01-01 00:15:00, 16509.78, 16534.66, 16509.11, 16533.43, 308.12276951,

Always add plenty of Moon Dev themed debug prints with emojis to make debugging easier! 🌙 ✨ 🚀
"""

DEBUG_PROMPT = """
You are Moon Dev's Debug AI 🌙
Fix technical issues in the backtest code WITHOUT changing the strategy logic.
Focus on:
1. Syntax errors (like incorrect string formatting)
2. Import statements and dependencies
3. Class and function definitions
4. Variable scoping and naming
5. Print statement formatting

DO NOT change:
1. Strategy logic
2. Entry/exit conditions
3. Risk management rules
4. Parameter values

Return the complete fixed code.
"""

def get_model_id(model):
    """Get DR/DC identifier based on model"""
    return "DR" if model == "deepseek-reasoner" else "DC"

import os
import time
import re
from datetime import datetime
import requests
from io import BytesIO
import PyPDF2
from youtube_transcript_api import YouTubeTranscriptApi
import openai
from pathlib import Path
from termcolor import cprint
import threading
import itertools
import sys

# DeepSeek Configuration
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Create necessary directories
DATA_DIR = Path("src/data/rbi")
RESEARCH_DIR = DATA_DIR / "research"
BACKTEST_DIR = DATA_DIR / "backtests"
FINAL_BACKTEST_DIR = DATA_DIR / "backtests_final"

for directory in [DATA_DIR, RESEARCH_DIR, BACKTEST_DIR, FINAL_BACKTEST_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

def init_deepseek_client():
    """Initialize DeepSeek client with proper error handling"""
    try:
        deepseek_key = os.getenv("DEEPSEEK_KEY")
        if not deepseek_key:
            raise ValueError("🚨 DEEPSEEK_KEY not found in environment variables!")
            
        client = openai.OpenAI(
            api_key=deepseek_key,
            base_url=DEEPSEEK_BASE_URL
        )
        cprint("🚀 Moon Dev's RBI Agent initialized with DeepSeek!", "green")
        return client
    except Exception as e:
        cprint(f"❌ Error initializing DeepSeek client: {e}", "red")
        return None

def chat_with_deepseek(system_prompt, user_content, model):
    """Chat with DeepSeek API using specified model"""
    client = init_deepseek_client()
    if not client:
        return None
        
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        cprint(f"❌ Error in DeepSeek chat: {e}", "red")
        return None

def get_youtube_transcript(video_id):
    """Get transcript from YouTube video"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_generated_transcript(['en'])
        cprint("📺 Successfully fetched YouTube transcript!", "green")
        return ' '.join([t['text'] for t in transcript.fetch()])
    except Exception as e:
        cprint(f"❌ Error fetching transcript: {e}", "red")
        return None

def get_pdf_text(url):
    """Extract text from PDF URL"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        reader = PyPDF2.PdfReader(BytesIO(response.content))
        text = ''
        for page in reader.pages:
            text += page.extract_text() + '\n'
        cprint("📚 Successfully extracted PDF text!", "green")
        return text
    except Exception as e:
        cprint(f"❌ Error reading PDF: {e}", "red")
        return None

def animate_progress(agent_name, stop_event):
    """Fun animation while agent is thinking"""
    spinners = ['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘']
    messages = [
        "brewing coffee ☕️",
        "studying charts 📊",
        "checking signals 📡",
        "doing math 🔢",
        "reading docs 📚",
        "analyzing data 🔍",
        "making magic ✨",
        "trading secrets 🤫",
        "Moon Dev approved 🌙",
        "to the moon! 🚀"
    ]
    
    spinner = itertools.cycle(spinners)
    message = itertools.cycle(messages)
    
    while not stop_event.is_set():
        sys.stdout.write(f'\r{next(spinner)} {agent_name} is {next(message)}...')
        sys.stdout.flush()
        time.sleep(0.5)
    sys.stdout.write('\r' + ' ' * 50 + '\r')
    sys.stdout.flush()

def run_with_animation(func, agent_name, *args, **kwargs):
    """Run a function with a fun loading animation"""
    stop_animation = threading.Event()
    animation_thread = threading.Thread(target=animate_progress, args=(agent_name, stop_animation))
    
    try:
        animation_thread.start()
        result = func(*args, **kwargs)
        return result
    finally:
        stop_animation.set()
        animation_thread.join()

def research_strategy(content):
    """Research Agent: Analyzes and creates trading strategy"""
    cprint("\n🔍 Starting Research Agent...", "cyan")
    cprint("🤖 Time to discover some alpha!", "yellow")
    
    output = run_with_animation(
        chat_with_deepseek,
        "Research Agent",
        RESEARCH_PROMPT, 
        content, 
        RESEARCH_MODEL
    )
    
    if output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = RESEARCH_DIR / f"strategy_{get_model_id(RESEARCH_MODEL)}_{timestamp}.txt"
        with open(filepath, 'w') as f:
            f.write(output)
        cprint(f"📝 Research Agent found something spicy! Saved to {filepath} 🌶️", "green")
        return output
    return None

def create_backtest(strategy):
    """Backtest Agent: Creates backtest implementation"""
    cprint("\n📊 Starting Backtest Agent...", "cyan")
    cprint("💰 Let's turn that strategy into profits!", "yellow")
    
    output = run_with_animation(
        chat_with_deepseek,
        "Backtest Agent",
        BACKTEST_PROMPT,
        f"Create a backtest for this strategy:\n\n{strategy}",
        BACKTEST_MODEL
    )
    
    if output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = BACKTEST_DIR / f"backtest_{get_model_id(BACKTEST_MODEL)}_{timestamp}.py"
        with open(filepath, 'w') as f:
            f.write(output)
        cprint(f"🔥 Backtest Agent cooked up some heat! Saved to {filepath} 🚀", "green")
        return output
    return None

def debug_backtest(backtest_code, strategy=None):
    """Debug Agent: Fixes technical issues in backtest code"""
    cprint("\n🔧 Starting Debug Agent...", "cyan")
    cprint("🔍 Time to squash some bugs!", "yellow")
    
    context = f"Here's the backtest code to debug:\n\n{backtest_code}"
    if strategy:
        context += f"\n\nOriginal strategy for reference:\n{strategy}"
    
    output = run_with_animation(
        chat_with_deepseek,
        "Debug Agent",
        DEBUG_PROMPT,
        context,
        DEBUG_MODEL
    )
    
    if output:
        code_match = re.search(r'```python\n(.*?)\n```', output, re.DOTALL)
        if code_match:
            output = code_match.group(1)
        return output
    return None

def process_trading_idea(idea):
    """Process a single trading idea through the RBI pipeline"""
    cprint("\n🚀 Moon Dev's RBI Agent Processing New Idea!", "cyan")
    cprint("🌟 Let's find some alpha in the chaos!", "yellow")
    
    # Extract content based on type
    if "youtube.com" in idea or "youtu.be" in idea:
        cprint("📺 YouTube strategy detected! Let's see what we can learn...", "cyan")
        video_id = re.search(r"(?:v=|\/)([a-zA-Z0-9_-]{11})(?:\?|$|&)", idea).group(1)
        content = get_youtube_transcript(video_id)
    elif idea.endswith('.pdf'):
        cprint("📚 PDF detected! Time to extract some knowledge...", "cyan")
        content = get_pdf_text(idea)
    else:
        cprint("💭 Processing raw strategy idea...", "cyan")
        content = idea
        
    if not content:
        cprint("❌ Failed to extract content", "red")
        return
        
    # Research Agent
    cprint("\n🧪 Phase 1: Research", "yellow")
    strategy = research_strategy(content)
    if not strategy:
        return
        
    # Backtest Agent
    cprint("\n📈 Phase 2: Backtest", "yellow")
    backtest = create_backtest(strategy)
    if not backtest:
        return
        
    # Debug Agent
    cprint("\n🔧 Phase 3: Debug", "yellow")
    debugged_backtest = debug_backtest(backtest, strategy)
    if debugged_backtest:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = FINAL_BACKTEST_DIR / f"backtest_final_{get_model_id(DEBUG_MODEL)}_{timestamp}.py"
        with open(filepath, 'w') as f:
            f.write(debugged_backtest)
        cprint(f"✨ Debug Agent made it shine! Final code saved to {filepath} 💎", "green")
    
    cprint("\n🎉 Mission Accomplished! All agents completed successfully!", "green")
    cprint("🚀 Ready to make it rain! 💸", "cyan")

def debug_existing_backtests():
    """Debug all existing backtests in the backtests directory"""
    cprint("\n🔍 Looking for existing backtests to debug...", "cyan")
    
    backtest_files = list(BACKTEST_DIR.glob("*.py"))
    if not backtest_files:
        cprint("❌ No backtest files found!", "yellow")
        return
        
    for backtest_file in backtest_files:
        cprint(f"\n🔧 Debugging {backtest_file.name}...", "cyan")
        
        # Read the backtest code
        with open(backtest_file, 'r') as f:
            backtest_code = f.read()
            
        # Try to find corresponding strategy file
        strategy_timestamp = backtest_file.stem.replace('backtest_', '')
        strategy_file = RESEARCH_DIR / f"strategy_{strategy_timestamp}.txt"
        strategy = None
        if strategy_file.exists():
            with open(strategy_file, 'r') as f:
                strategy = f.read()
                
        # Debug the backtest
        debugged_code = debug_backtest(backtest_code, strategy)
        if debugged_code:
            output_file = FINAL_BACKTEST_DIR / f"backtest_final_{get_model_id(DEBUG_MODEL)}_{backtest_file.name}"
            with open(output_file, 'w') as f:
                f.write(debugged_code)
            cprint(f"✨ Saved debugged version to {output_file}", "green")
        else:
            cprint(f"❌ Failed to debug {backtest_file.name}", "red")

def main():
    """Main function to process ideas from file"""
    ideas_file = Path("src/data/rbi/ideas.txt")
    
    if not ideas_file.exists():
        cprint("❌ ideas.txt not found! Creating template...", "red")
        ideas_file.parent.mkdir(parents=True, exist_ok=True)
        with open(ideas_file, 'w') as f:
            f.write("# Add your trading ideas here (one per line)\n")
            f.write("# Can be YouTube URLs, PDF links, or text descriptions\n")
        return
        
    with open(ideas_file, 'r') as f:
        ideas = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
    for i, idea in enumerate(ideas, 1):
        cprint(f"\n🌙 Processing idea {i}/{len(ideas)}", "cyan")
        process_trading_idea(idea)
        time.sleep(2)  # Prevent rate limiting

if __name__ == "__main__":
    try:
        cprint(f"\n🌟 Moon Dev's RBI Agent Starting Up with {RESEARCH_MODEL} and {BACKTEST_MODEL}!", "green")
        main()
    except KeyboardInterrupt:
        cprint("\n👋 Moon Dev's RBI Agent shutting down gracefully...", "yellow")
    except Exception as e:
        cprint(f"\n❌ Fatal error: {str(e)}", "red")
