package com.atlas.ragengine.qa;

import java.util.List;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import org.springframework.ai.chat.prompt.Prompt;

/** Deterministic, offline {@link ChatModel} stub: returns a fixed answer and counts invocations. */
public class StubChatModel implements ChatModel {

    private final String answer;
    private int calls;
    private Prompt lastPrompt;

    public StubChatModel(String answer) {
        this.answer = answer;
    }

    @Override
    public ChatResponse call(Prompt prompt) {
        this.calls++;
        this.lastPrompt = prompt;
        return new ChatResponse(List.of(new Generation(new AssistantMessage(answer))));
    }

    public int calls() {
        return calls;
    }

    public Prompt lastPrompt() {
        return lastPrompt;
    }
}
