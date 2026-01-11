# AI-Assisted Service Search Prompts

This directory contains the prompts used for the AI-assisted service search feature. The AI search process follows a two-step approach to help users find relevant IT services based on their problem description.

## Process Overview

### Step 1: Initial Problem Evaluation
The AI receives:
- The user's problem description
- A list of all currently listed services (name, key, purpose in user's language)

The AI evaluates:
- Whether the problem is related to IT services
- Which services might be relevant for detailed evaluation
- Returns service keys for further inspection

### Step 2: Detailed Service Evaluation (if needed)
The AI receives:
- The conversation history from Step 1
- Detailed information about the requested services (all public fields)

The AI evaluates:
- Which services actually address the user's problem
- Prioritizes and recommends up to 3 services
- Provides guidance on what to check in each service

## Prompt Files

### `step1_prompt.txt`
System prompt for the initial evaluation phase. This prompt instructs the AI to:
- Determine if the user's problem is IT service-related
- Identify potentially relevant services from the catalogue
- Request detailed information for further evaluation
- Respond in the user's language

### `step2_prompt.txt`
System prompt for the detailed evaluation phase. This prompt instructs the AI to:
- Analyze detailed service information
- Match services to the user's specific problem
- Recommend up to 3 most relevant services with explanations
- List services that were evaluated but not recommended
- Respond in the user's language

## Customization

Both prompts can be customized by:
1. Directly editing the files in this directory
2. Using Docker volume overlays to replace the prompts without modifying the container

The prompts are written in English but instruct the AI to respond in the user's language. State-of-the-art language models handle this cross-lingual instruction well.

## Important Notes

- The AI communication is not shown to users (only progress indicators)
- User input and AI responses are NOT logged for privacy reasons
- Only metadata (requested services, recommended services, token usage) is logged for analytics
- The process is designed to be transparent through progress updates, not detailed AI communication logs
