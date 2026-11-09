export type HeaderBannerSegment = {
  type: "text" | "link";
  value?: string;
  text?: string;
  href?: string;
};

export type HeaderBannerData = {
  is_active: boolean;
  language: string;
  segments: HeaderBannerSegment[];
  plain_text?: string;
  source_url?: string;
  content_hash?: string;
  scrapedAt?: string;
  createdAt?: string;
  updatedAt?: string;
};

export type HeaderBannerResponse = {
  success: boolean;
  message?: string;
  data?: HeaderBannerData;
};
