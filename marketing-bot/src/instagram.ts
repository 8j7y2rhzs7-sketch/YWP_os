export class InstagramPublisher {
  constructor(
    private readonly graphVersion: string,
    private readonly userId: string,
    private readonly accessToken: string
  ) {}

  private async post(path: string, body: Record<string, string>): Promise<Record<string, unknown>> {
    const response = await fetch(`https://graph.facebook.com/${this.graphVersion}/${path}`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ ...body, access_token: this.accessToken }),
      signal: AbortSignal.timeout(30_000)
    });
    const payload = await response.json() as Record<string, unknown>;
    if (!response.ok) throw new Error(`Instagram API error ${response.status}: ${JSON.stringify(payload)}`);
    return payload;
  }

  async publishImage(imageUrl: string, caption: string): Promise<string> {
    if (!this.userId || !this.accessToken) throw new Error("Instagram credentials are not configured.");
    const container = await this.post(`${this.userId}/media`, { image_url: imageUrl, caption });
    const creationId = String(container.id ?? "");
    if (!creationId) throw new Error("Instagram did not return a media container ID.");
    const result = await this.post(`${this.userId}/media_publish`, { creation_id: creationId });
    const mediaId = String(result.id ?? "");
    if (!mediaId) throw new Error("Instagram did not return a published media ID.");
    return mediaId;
  }
}
