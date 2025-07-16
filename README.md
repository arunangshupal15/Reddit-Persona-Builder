# Reddit Persona Builder

This tool extracts a user persona from a Reddit profile using the Together AI API and outputs a detailed Markdown summary, including demographics, personality traits, motivations, behaviors, frustrations, goals, and a generated quote.

## Features

- Fetches recent comments and posts from a Reddit user
- Uses an LLM (Together AI) to extract persona traits
- Outputs a structured Markdown persona file
- Handles ambiguous/empty results gracefully

## Requirements

- Python 3.8+
- Reddit API credentials (client ID, client secret, user agent)
- Together AI API key

## Installation

1. **Clone or download this repository.**
2. **Install dependencies:**
   ```bash
   pip install praw requests
   ```

## Configuration

- Edit the top of `reddit_persona_builder.py` to set your Reddit API credentials and Together AI API key:
  ```python
  REDDIT_CLIENT_ID = "your_client_id"
  REDDIT_CLIENT_SECRET = "your_client_secret"
  REDDIT_USER_AGENT = "your_user_agent"
  TOGETHER_API_KEY = "your_together_api_key"
  ```

## Usage

Run the script from the command line with the required arguments:

```bash
python reddit_persona_builder.py --url <reddit_user_profile_url> --output <output_markdown_file>
```

- `<reddit_user_profile_url>`: The full URL to the Reddit user's profile (e.g., `https://www.reddit.com/user/kojied/`)
- `<output_markdown_file>`: The filename for the generated persona Markdown file (e.g., `persona_kojied.md`)

### Example

```bash
python reddit_persona_builder.py --url https://www.reddit.com/user/kojied/ --output persona_kojied.md
```

## Output

- The script will create a Markdown file summarizing the user's persona traits, motivations, behaviors, frustrations, goals, and a generated quote.
- If insufficient data is found, the output file will indicate this.

## Troubleshooting

- If you see errors about API keys, double-check your credentials.
- If the output is empty, the Reddit user may not have enough public activity, or the LLM may not extract traits from the available data.
