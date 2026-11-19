import type { Item } from "@/lib/items";
import type { SaleStatus } from "@/lib/data";

export const EARLY_MAX_DAYS = 90;
export const EARLY_MAX_POSTINGS = 3;

export function hasIssuerSale(item: Item): boolean {
  const sale = item.raise;
  return !!sale?.firstSale && sale.kind === "sold" && sale.sold !== null && sale.sold > 0;
}

export function isEarly(item: Item): boolean {
  const sale = item.raise;
  const count = sale?.hiring.observed_postings_since_signal;
  return (
    hasIssuerSale(item) &&
    !!sale &&
    sale.days >= 0 &&
    sale.days <= EARLY_MAX_DAYS &&
    item.onNetwork &&
    item.openRoles !== null &&
    sale.hiring.hiring_coverage === "since_signal" &&
    count != null &&
    count <= EARLY_MAX_POSTINGS
  );
}

export const saleLabels: Record<SaleStatus, string> = {
  recent_first_sale: "First vehicle sale in this window",
  historical_first_sale: "First vehicle sale before this window",
  sale_date_unknown: "Vehicle sale date unknown",
  no_sales_reported: "No vehicle sales reported",
  unknown: "Vehicle sale information incomplete",
};

export function vehicleStatus(status: SaleStatus | undefined, sold: number | null): SaleStatus {
  if (status) return status;
  if (sold === null) return "unknown";
  return sold > 0 ? "sale_date_unknown" : "no_sales_reported";
}
