We have a chat prompt that runs a product-requirements interview. A product person pastes it into Claude.ai or ChatGPT, and the assistant interviews them and produces a PRD. We now want the same thing on a **local model**: Qwen 3.5 35B-A3B under Ollama, used through a plain chat UI. The prompt goes in as the system message. The user's first message is their feature idea.

Here is the current prompt:

<current_prompt>
{{CURRENT_PROMPT}}
</current_prompt>

Port it to the local model. Keep what the interview must achieve: the eight PRD sections, an interview that goes one question at a time, requirements only (WHAT and WHY, no HOW), and the final document as Markdown. Adapt everything else as you see fit for this model and setting.

Return only the new system prompt, between `<prompt>` and `</prompt>`.
