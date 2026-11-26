export type LibraryVersion = {
  id: string;
  asset_id: string;
  version: number;
  filename: string;
  sha256: string;
  size: number;
  mime: string;
  origin: string;
  available: boolean;
  created_at: string;
  has_text_snapshot: boolean;
  text_snapshot?: { number: number; label: string; text: string }[];
};
export type LibraryAsset = {
  id: string;
  workspace_id: string;
  title: string;
  category: string;
  subject_id: string | null;
  subject_name: string | null;
  subject_label: string | null;
  subject_archived: boolean;
  archived: boolean;
  inbox: boolean;
  revision: number;
  latest: LibraryVersion | null;
  case_count: number;
  created_at: string;
  updated_at: string;
};
export type LibraryDetail = LibraryAsset & {
  versions: LibraryVersion[];
  usages: {
    case_id: string;
    case_title: string;
    document_id: string;
    asset_revision_id: string;
    version: number;
    active: boolean;
    purpose: string;
  }[];
};
export type LibraryList = {
  items: LibraryAsset[];
  total: number;
  limit: number;
  offset: number;
};
export type Duplicate = {
  asset_id: string;
  title: string;
  revision_id: string;
  version: number;
  archived: boolean;
};
export type UploadResult = { asset: LibraryDetail; duplicates: Duplicate[] };
export function fileSize(size: number) {
  return size >= 1024 * 1024
    ? (size / (1024 * 1024)).toFixed(1) + " MiB"
    : size >= 1024
      ? (size / 1024).toFixed(1) + " KiB"
      : size + " B";
}
