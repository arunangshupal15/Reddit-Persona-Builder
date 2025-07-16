
import argparse
import json
import re
import sys
import time
from collections import defaultdict

import praw
import requests

REDDIT_CLIENT_ID = "EQ9tIFU4MdN0a00ZP78NgA"
REDDIT_CLIENT_SECRET = "mISxIPIyUoRM5fOPab6b0eAPn8rAOg"
REDDIT_USER_AGENT = "reddit_persona_builder/v1.0 (by /u/Dark-trespasser)"

TOGETHER_API_KEY = "f62b6050680231337ded5b562241691bcb46caff185d9ad8d8f68d2dc51c669b"
TOGETHER_API_URL = "https://api.together.ai/inference"
TOGETHER_MODEL = "meta-llama/Llama-4-Scout-17B-16E-Instruct"  
categories = [
    "Demographics", "Personality Traits", "Motivations",
    "Behaviors & Habits", "Frustrations", "Goals & Needs"
]

reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)

extract_prompt_template = """
Analyze the following Reddit text and extract user persona information. For each piece of information found, format it exactly as "Category: specific detail".

Use these categories:
- Demographics: age, location, occupation, relationship status
- Personality Traits: introvert/extrovert, interests, communication style
- Motivations: what drives them, values, priorities
- Behaviors & Habits: daily routines, preferences, patterns
- Frustrations: complaints, dislikes, problems they face
- Goals & Needs: what they want to achieve, what they need

Text: "{text}"

Only output lines in the format "Category: detail". If no relevant information is found, output "No relevant information found."
"""

quote_prompt_template = """
Based on this user persona, create a short, natural quote (1-2 sentences) that this person might say. Make it sound authentic and reflect their personality.

Persona:
{persona_summary}

Quote:"""


def safe_request(url, headers, payload, retries=3):
    for attempt in range(retries):
        try:
            print(f"[DEBUG] Making API request (attempt {attempt + 1})")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            print(f"[DEBUG] Response status: {response.status_code}")
            if response.status_code != 200:
                print(f"[DEBUG] Response content: {response.text}")
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            print(f"[WARN] Request error (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                time.sleep(2)
        except ValueError as e:
            print(f"[ERROR] JSON decoding error: {e}")
            print(f"Response text:\n{response.text}")
            return None
    print("[ERROR] All retries failed.")
    return None


def parse_together_output(data):
    if not data:
        return None

    
    if isinstance(data, dict):
        if "output" in data:
            if isinstance(data["output"], str):
                return data["output"].strip()
            elif isinstance(data["output"], dict) and "choices" in data["output"]:
                choices = data["output"]["choices"]
                if choices and "text" in choices[0]:
                    return choices[0]["text"].strip()

        if "choices" in data:
            choices = data["choices"]
            if choices and "text" in choices[0]:
                return choices[0]["text"].strip()
            elif choices and "message" in choices[0]:
                return choices[0]["message"]["content"].strip()

        if "text" in data:
            return data["text"].strip()

    print(f"[DEBUG] Unexpected response format: {data}")
    return None



def extract_characteristics(text):
    if len(text.strip()) < 20:
        return defaultdict(list)

    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": TOGETHER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": extract_prompt_template.format(text=text[:1000])  
            }
        ],
        "max_tokens": 300,
        "temperature": 0.3
    }

    time.sleep(1.1)  
    data = safe_request(TOGETHER_API_URL, headers, payload)
    output = parse_together_output(data)

    print(f"\n[DEBUG] Input text (first 100 chars): {text[:100]}...")
    print(f"[DEBUG] Raw extraction output: {output}")
    print()

    characteristics = defaultdict(list)
    if output and output.strip() != "No relevant information found.":
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            match = re.match(
                r"^(Demographics|Personality|Personality Traits|Motivations|Behaviors?|Habits|Behaviors & Habits|Frustrations|Goals|Needs|Goals & Needs)\s*:\s*(.+)$",
                line, re.I
            )
            if match:
                category_raw, characteristic = match.group(1), match.group(2).strip()

                
                category = None
                for cat in categories:
                    if (
                        cat.lower().replace(" ", "").replace("&", "") ==
                        category_raw.lower().replace(" ", "").replace("&", "")
                    ):
                        category = cat
                        break
                    elif cat.lower().startswith(category_raw.lower().split()[0]):
                        category = cat
                        break

                if category and category in categories:
                    characteristics[category].append(characteristic)
                    print(f"[DEBUG] Extracted: {category} -> {characteristic}")

    return characteristics


def generate_quote(persona_summary):
    if not persona_summary or persona_summary.strip() == "No persona traits found.":
        return "No quote available."
    
    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": TOGETHER_MODEL,
        "messages": [
            {"role": "user", "content": quote_prompt_template.format(persona_summary=persona_summary)}
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }
    
    time.sleep(1.1)
    data = safe_request(TOGETHER_API_URL, headers, payload)
    output = parse_together_output(data)

    print(f"\n[DEBUG] Generated quote: {output}")
    print()

    if output:
        quote = output.strip()
        if quote.lower().startswith("quote:"):
            quote = quote[6:].strip()
        return quote if quote else "No quote available."
    
    return "No quote available."


def get_username_from_url(url):
    match = re.search(r"/user/([^/?#]+)/?", url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Reddit user URL")


def get_user_activity(username, limit=50):  
    try:
        redditor = reddit.redditor(username)
        activity = []
        
        print(f"[INFO] Fetching comments for {username}...")
        comment_count = 0
        for comment in redditor.comments.new(limit=limit):
            if comment.body and comment.body != "[deleted]" and comment.body != "[removed]":
                activity.append({
                    "text": comment.body,
                    "source": f"https://www.reddit.com{comment.permalink}",
                    "type": "comment"
                })
                comment_count += 1
        
        print(f"[INFO] Fetching posts for {username}...")
        post_count = 0
        for post in redditor.submissions.new(limit=limit):
            text = ""
            if post.is_self and post.selftext:
                text = post.selftext
            elif post.title:
                text = post.title
            
            if text and text != "[deleted]" and text != "[removed]":
                activity.append({
                    "text": text,
                    "source": f"https://www.reddit.com{post.permalink}",
                    "type": "post"
                })
                post_count += 1
        
        print(f"[INFO] Found {comment_count} comments and {post_count} posts")
        return activity
        
    except Exception as e:
        print(f"[ERROR] Reddit fetch error: {e}")
        return []


def render_persona_markdown(username, profile_data, quote, sources_data):
    summary_fields = {
        "Name": username,
        "Age": "",
        "Occupation": "",
        "Status": "",
        "Location": "",
        "Archetype": "",
        "Tier": ""
    }
    for item in profile_data.get("Demographics", []):
        #Age
        m = re.search(r"(\d{2})\b", item)
        if m:
            summary_fields["Age"] = m.group(1)
        #Occupation
        if any(word in item.lower() for word in ["manager", "engineer", "student", "designer", "writer", "developer", "teacher", "analyst", "consultant", "doctor", "nurse", "chef", "artist", "scientist", "researcher", "content"]):
            summary_fields["Occupation"] = item
        #Status
        if any(word in item.lower() for word in ["single", "married", "divorced", "widow", "relationship"]):
            summary_fields["Status"] = item
        #Location
        if any(word in item.lower() for word in ["uk", "us", "india", "canada", "australia", "germany", "france", "london", "new york", "delhi", "paris", "tokyo", "city", "state", "country"]):
            summary_fields["Location"] = item
    #Archetype and Tier
    for trait in profile_data.get("Personality Traits", []):
        if any(word in trait.lower() for word in ["creator", "innovator", "early adopter", "leader", "follower", "adopter"]):
            summary_fields["Archetype"] = trait
        if any(word in trait.lower() for word in ["early adopter", "late adopter", "mainstream", "tier"]):
            summary_fields["Tier"] = trait

    lines = []
    lines.append(f"# {summary_fields['Name']}")
    lines.append("")
    lines.append("| Age | Occupation | Status | Location | Tier | Archetype |\n|---|---|---|---|---|---|")
    lines.append(f"| {summary_fields['Age']} | {summary_fields['Occupation']} | {summary_fields['Status']} | {summary_fields['Location']} | {summary_fields['Tier']} | {summary_fields['Archetype']} |")
    lines.append("")
    def is_ambiguous(val):
        v = val.strip().lower()
        return (
            v in ["no relevant information found.", "no specific detail", "none", "n/a", "not specified", "not mentioned", "unknown", "unspecified", "no detail", "no details"]
            or v == ""
        )

    #Key traits
    key_traits = []
    for trait in profile_data.get("Personality Traits", []):
        if is_ambiguous(trait):
            if trait.strip().lower() == "no relevant information found.":
                key_traits.append(trait)
            continue
        if any(word in trait.lower() for word in ["practical", "adaptable", "spontaneous", "active", "creative", "analytical", "organized", "social", "introvert", "extrovert"]):
            key_traits.append(trait.capitalize())
    if key_traits:
        lines.append("**Key Traits:** " + " | ".join(key_traits))
        lines.append("")

    lines.append("## Motivations\n")
    motivations = [m for m in profile_data.get("Motivations", []) if not is_ambiguous(m)]
    if motivations:
        for m in motivations:
            bar = "█" * min(10, max(2, len(m) // 8))
            lines.append(f"- {m} {bar}")
    else:
        lines.append("_No data found._")
    lines.append("")
    lines.append("## Personality\n")
    trait_pairs = [
        ("Introvert", "Extrovert"),
        ("Intuition", "Sensing"),
        ("Feeling", "Thinking"),
        ("Perceiving", "Judging")
    ]
    for left, right in trait_pairs:
        left_score = sum(1 for t in profile_data.get("Personality Traits", []) if left.lower() in t.lower() and not is_ambiguous(t))
        right_score = sum(1 for t in profile_data.get("Personality Traits", []) if right.lower() in t.lower() and not is_ambiguous(t))
        total = left_score + right_score
        if total == 0:
            bar = "[ ]" * 5
        else:
            left_bar = "█" * left_score
            right_bar = "█" * right_score
            bar = f"{left_bar:<5}|{right_bar:>5}"
        lines.append(f"{left:<10} {bar} {right:>10}")
    lines.append("")

    lines.append(f'> **"{quote}"**\n')

    lines.append("## Behaviour & Habits\n")
    behaviors = [b for b in profile_data.get("Behaviors & Habits", []) if not is_ambiguous(b)]
    if behaviors:
        for b in behaviors:
            lines.append(f"- {b}")
    else:
        lines.append("_No data found._")
    lines.append("")

    #Frustrations
    lines.append("## Frustrations\n")
    frustrations = [f for f in profile_data.get("Frustrations", []) if not is_ambiguous(f)]
    if frustrations:
        for f in frustrations:
            lines.append(f"- {f}")
    else:
        lines.append("_No data found._")
    lines.append("")

    #Goals & Needs
    lines.append("## Goals & Needs\n")
    goals = [g for g in profile_data.get("Goals & Needs", []) if not is_ambiguous(g)]
    if goals:
        for g in goals:
            lines.append(f"- {g}")
    else:
        lines.append("_No data found._")
    lines.append("")
    return "\n".join(lines)


def build_user_persona(url, output_file):
    try:
        username = get_username_from_url(url)
    except ValueError as ve:
        print(ve)
        sys.exit(1)

    print(f"[INFO] Fetching Reddit activity for user: {username}")
    activity = get_user_activity(username)
    
    if not activity:
        with open(output_file, "w") as f:
            f.write(f"# {username}\n\nNo activity found to build a persona.")
        print(f"[INFO] Insufficient data. Output saved to {output_file}")
        return

    print(f"[INFO] Processing {len(activity)} items...")
    extracted_data = defaultdict(list)
    
    for i, act in enumerate(activity):
        print(f"[INFO] Processing item {i+1}/{len(activity)}")
        characteristics = extract_characteristics(act["text"])
        
        for category, chars in characteristics.items():
            for char in chars:
                extracted_data[category].append({
                    "characteristic": char, 
                    "source": act["source"]
                })

    sources_data = {cat: defaultdict(list) for cat in categories}
    profile_data = {cat: [] for cat in categories}
    
    for category, items in extracted_data.items():
        char_sources = defaultdict(list)
        for item in items:
            char_sources[item["characteristic"]].append(item["source"])
        
        for char, sources in char_sources.items():
            profile_data[category].append(char)
            sources_data[category][char] = sources

    #Create summary for quote generation
    persona_summary_text = ""
    total_traits = 0
    for category in categories:
        if profile_data.get(category):
            persona_summary_text += f"{category}:\n"
            for item in profile_data[category]:
                persona_summary_text += f"- {item}\n"
                total_traits += 1
            persona_summary_text += "\n"

    if total_traits == 0:
        persona_summary_text = "No persona traits found."
    
    print(f"[INFO] Found {total_traits} total traits")
    print(f"[DEBUG] Persona summary:\n{persona_summary_text}")

    quote = generate_quote(persona_summary_text)
    final_markdown = render_persona_markdown(username, profile_data, quote, sources_data)

    with open(output_file, "w", encoding='utf-8') as f:
        f.write(final_markdown)
    print(f"[SUCCESS] Persona for {username} saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a user persona from a Reddit profile.")
    parser.add_argument("--url", required=True, help="Reddit user profile URL (e.g., https://www.reddit.com/user/kojied/)")
    parser.add_argument("--output", required=True, help="Output file for the persona (e.g., persona_kojied.md)")
    args = parser.parse_args()

    try:
        build_user_persona(args.url, args.output)
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()