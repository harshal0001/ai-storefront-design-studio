/**
 * Fallback zone-tour chat intros when API message/prompt are empty.
 *
 * Keep in sync with backend ``zone_catalog`` copy. ``buildZoneTourChatMessage`` composes
 * the assistant bubble shown when a tour step advances.
 */
const ZONE_CHAT_INTRO = {
  Z1: "Pick a swatch below — each label says exactly which part of the preview it changes.",
  Z2: "These options change the banner photo area, logo placement, and store name on the hero.",
  Z3: "These options change fonts and text size on intro and store information sections.",
  Z4: "Choose backgrounds per product section, card layout, then how prices display on cards.",
  Z5: "Offer cards are managed by the platform — read the note below, then continue.",
  Z6: "These options change the Follow button, coupon buttons, and other call-to-action buttons.",
};

export function zoneChatIntro(zone) {
  if (!zone) return "";
  return ZONE_CHAT_INTRO[zone] || "";
}

export function buildZoneTourChatMessage(data) {
  const intro =
    data.message ||
    data.zone_tour?.current_prompt ||
    [
      data.zone_tour?.current_zone_name,
      data.zone_tour?.current_headline,
      zoneChatIntro(data.zone_tour?.current_zone),
    ]
      .filter(Boolean)
      .join("\n\n");
  return {
    role: "assistant",
    text: intro,
    type: "zone_tour",
    zone_tour: data.zone_tour,
    color_options: data.color_options,
    zone_options: data.zone_options,
    theme_packages: data.theme_packages,
    vibe_options: data.vibe_options,
  };
}

export function messageHasTourOptions(msg) {
  if (!msg || msg.role !== "assistant") return false;
  const isActiveTour = Boolean(msg.zone_tour?.active);
  return (
    isActiveTour ||
    (msg.color_options?.length ?? 0) > 0 ||
    (msg.zone_options?.length ?? 0) > 0 ||
    (msg.vibe_options?.length ?? 0) > 0 ||
    (msg.theme_packages?.length ?? 0) > 0
  );
}
