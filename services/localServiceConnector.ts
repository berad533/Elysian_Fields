
/**
 * A versatile connector for a suite of local, self-hosted AI services.
 * This class reroutes AI function calls to their corresponding local server endpoints.
 */
export class LocalServiceConnector {
  /**
   * A shared, private error handler for consistent error messages.
   * It attempts to parse JSON error responses for more specific details.
   * @param error The catched error object.
   * @param serviceName The name of the service that failed (e.g., 'Chat', 'OCR').
   * @param response The optional Fetch API Response object if the error was an HTTP error.
   * @returns A promise that always rejects with a user-friendly error message.
   */
  private async _handleApiError(error: any, serviceName: string, response?: Response): Promise<never> {
    console.error(`Error calling local ${serviceName} service:`, error, response);
    let errorMessage: string;

    // Case 1: We have an HTTP response object, meaning the server replied with an error status.
    if (response) {
        errorMessage = `The ${serviceName} server responded with status: ${response.status}.`;
        try {
            const errorBody = await response.json();
            // Attempt to extract a more specific message from common error schemas.
            const detail = errorBody.error?.message || errorBody.detail || errorBody.message;
            if (typeof detail === 'string' && detail.trim()) {
                errorMessage = `${serviceName} service error: ${detail}`;
            }
        } catch (e) {
            // The error response was not JSON or was empty. The status code is the best we have.
            console.warn(`Could not parse JSON from ${serviceName} error response.`);
        }
    } 
    // Case 2: We have a standard Error object, likely from a network failure.
    else if (error instanceof Error) {
        const msg = error.message.toLowerCase();
        if (msg.includes('failed to fetch')) {
            errorMessage = `Could not connect to the local ${serviceName} service. Ensure it's running and CORS is enabled.`;
        } else {
            // For other errors (e.g., JSON parsing on a successful response), use the message.
            errorMessage = error.message;
        }
    } 
    // Case 3: Fallback for unknown error types.
    else {
        errorMessage = `An unknown error occurred with the local ${serviceName} service.`;
    }
    
    throw new Error(errorMessage);
  }

  /**
   * Sends a chat completion request to a local LLM server (e.g., LM Studio).
   * @param messages The array of messages for the chat.
   * @param options Configuration options like temperature and max_tokens.
   * @returns The content of the assistant's response as a string.
   */
  async getChatCompletion(
    messages: { role: string; content: string }[],
    options: { temperature?: number; max_tokens?: number } = {}
  ): Promise<string> {
    const { temperature = 0.2, max_tokens } = options;

    const body: { [key: string]: any } = {
        model: "local-model", // This is often a placeholder in LM Studio
        messages: messages,
        temperature: temperature,
    };
    if (max_tokens) {
        body.max_tokens = max_tokens;
    }

    try {
      const response = await fetch("http://127.0.0.1:1234/v1/chat/completions", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw { response }; // Throw response to be handled by the catch block
      }

      const data = await response.json();
      const content = data.choices[0]?.message?.content;

      if (!content) {
        throw new Error("Local AI returned an empty or invalid response.");
      }
      return content;
    } catch (error: any) {
      if (error.response) {
        return this._handleApiError(null, 'Chat', error.response);
      }
      return this._handleApiError(error, 'Chat');
    }
  }

  /**
   * Sends an image to a local OCR server for text extraction.
   * @param base64Image The base64-encoded image string.
   * @param mimeType The MIME type of the image.
   * @param settings The connection settings for the local OCR server.
   * @returns An object containing the extracted text.
   */
  async performOcr(base64Image: string, mimeType: string, settings: { url: string; apiKey?: string }): Promise<{ text: string }> {
    const { url, apiKey } = settings;
    if (!url || !url.trim()) {
        throw new Error("Local OCR URL is not configured.");
    }
    const headers: HeadersInit = { 'Content-Type': 'application/json' };
    if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
    }

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          image: base64Image,
          mime_type: mimeType,
        }),
      });

      if (!response.ok) {
        throw { response };
      }

      return await response.json();
    } catch (error: any) {
      if (error.response) {
        return this._handleApiError(null, 'OCR', error.response);
      }
      return this._handleApiError(error, 'OCR');
    }
  }

  /**
   * Sends a text prompt to a local image generation server (e.g., Stable Diffusion).
   * @param prompt The text prompt for image generation.
   * @param params Additional parameters like width, height, and steps.
   * @returns An object containing an array of base64-encoded generated images.
   */
  async generateImage(
    prompt: string,
    params: { width?: number; height?: number; steps?: number } = {}
  ): Promise<{ images: string[] }> {
    const { width = 512, height = 512, steps = 20 } = params;
    try {
      const response = await fetch("http://localhost:7860/sdapi/v1/txt2img", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt,
          width: width,
          height: height,
          steps: steps,
        }),
      });

      if (!response.ok) {
        throw { response };
      }
      
      return await response.json();
    } catch (error: any) {
      if (error.response) {
        return this._handleApiError(null, 'Image Generation', error.response);
      }
      return this._handleApiError(error, 'Image Generation');
    }
  }

  /**
   * Tests the connection to the local LLM server by sending a simple ping message.
   * @returns A promise that resolves to an object indicating success and a message.
   */
  async testConnection(): Promise<{ success: boolean; message: string; }> {
    try {
        await this.getChatCompletion(
            [{ role: "user", content: "ping" }],
            { max_tokens: 10 }
        );
        return { success: true, message: 'Connection successful!' };
    } catch (error: any) {
        console.error("Local connection test failed:", error);
        return { success: false, message: error.message };
    }
  }

  /**
   * Tests the connection to the local OCR server.
   * @param settings The connection settings for the local OCR server.
   * @returns A promise that resolves to an object indicating success and a message.
   */
  async testOcrConnection(settings: { url: string; apiKey?: string }): Promise<{ success: boolean; message: string; }> {
    try {
        // A 1x1 black pixel PNG
        const dummyImage = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";
        await this.performOcr(dummyImage, 'image/png', settings);
        return { success: true, message: 'Connection successful!' };
    } catch (error: any) {
        console.error("Local OCR connection test failed:", error);
        return { success: false, message: error.message };
    }
  }

  /**
   * Tests the connection to the local image generation server.
   * @returns A promise that resolves to an object indicating success and a message.
   */
  async testImageGenConnection(): Promise<{ success: boolean; message: string; }> {
    try {
        await this.generateImage("connection test", { width: 64, height: 64, steps: 1 });
        return { success: true, message: 'Connection successful!' };
    } catch (error: any) {
        console.error("Local Image Gen connection test failed:", error);
        return { success: false, message: error.message };
    }
  }
}

/**
 * A hypothetical function to establish a connection to a local LLM.
 * It sends a POST request to the standard LM Studio endpoint with a simple
 * JSON object formatted for the OpenAI chat completions API.
 * @returns A promise that resolves with the full JSON response from the server.
 * @throws An error if the network request or server response fails.
 */
export async function establishLocalLlmConnection(): Promise<any> {
  const body = {
    model: "local-model", // A placeholder often used for LM Studio
    messages: [
      {
        role: "user",
        content: "This is a connection test from the Universal Confluence Protocol."
      }
    ]
  };

  const response = await fetch("http://127.0.0.1:1234/v1/chat/completions", {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let errorDetail = await response.text();
    try {
        const errorJson = JSON.parse(errorDetail);
        // Extract a more specific message if available from common error schemas.
        errorDetail = errorJson.error?.message || errorJson.detail || errorJson.message || errorDetail;
    } catch(e) { 
        // Ignore if the error body isn't JSON.
    }
    throw new Error(`Local LLM server responded with an error. Status: ${response.status}. Detail: ${errorDetail}`);
  }

  return await response.json();
}