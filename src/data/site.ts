// SATGAS — single source of truth for page content.
// Sample details (project titles, crew names, addresses) are marked in the report
// for the client to confirm before launch. No invented proof: no client logos,
// no testimonials, no statistics we cannot stand behind.

export const nav = [
  { label: "Missions", href: "#missions" },
  { label: "Services", href: "#services" },
  { label: "Team", href: "#team" },
  { label: "Contact", href: "#contact" },
];

export const marquee = [
  "Taking on 2 missions this quarter",
  "HQ in Central Jakarta",
  "Since 2024",
  "7 crew, deliberately small",
  "Brief in, unit assembled, task force disbanded",
  "Reply within 1 business day",
];

export const facts = [
  { label: "HQ", value: "Central Jakarta" },
  { label: "Founded", value: "2024" },
  { label: "Crew", value: "Seven" },
  { label: "Status", value: "Open" },
];

export type Category = "Identity" | "Campaign" | "Wayfinding" | "Film" | "Website" | "AI";

export const categories: Array<Category | "All"> = [
  "All",
  "Identity",
  "Campaign",
  "Wayfinding",
  "Film",
  "Website",
  "AI",
];

export interface Project {
  id: string;
  title: string;
  category: Category;
  year: string;
  blurb: string;
  image: string;
  alt: string;
  delivered: string[];
  result: string;
}

export const projects: Project[] = [
  {
    id: "kopi-titik",
    title: "Dot Coffee",
    category: "Identity",
    year: "2025",
    blurb:
      "A logo born from the colon on the bottle label: one pause before service begins.",
    image: "assets/kopi-dripper.jpg",
    alt: "Water filtered through a coffee dripper, detail of the brewing process",
    delivered: [
      "Colon logogram drawn from the shop's original bottle label",
      "Used on cups, aprons, and the six-metre timber facade",
      "Single-colour guide: black, paper, one blue",
    ],
    result: "The shop opened with one mark across seven touchpoints.",
  },
  {
    id: "taksi-90",
    title: "Taxi 90",
    category: "Campaign",
    year: "2025",
    blurb:
      "Road-marking typography read as the number 90 from a low angle.",
    image: "assets/jakarta-kota-station.jpg",
    alt: "Jakarta Kota Station, site of the transport campaign",
    delivered: [
      "Type system drawn from road markings and zebra crossings",
      "Installed at 14 shelters along the central corridor",
      "Print version for tickets and transit-pass covers",
    ],
    result: "A ninety-day street campaign without a single billboard.",
  },
  {
    id: "papan-kita",
    title: "Our Signs",
    category: "Wayfinding",
    year: "2024",
    blurb:
      "Direction arrows redrawn by residents, not an unfamiliar standard.",
    image: "assets/hands-faders.jpg",
    alt: "Hands adjusting faders on an audio console, sound design in progress",
    delivered: [
      "Wayfinding system for an urban village",
      "Three board sizes, one arrow shape",
      "Sound cues for routes you cannot see",
    ],
    result: "Residents give directions by board name, not by number.",
  },
  {
    id: "bulan-sabit",
    title: "Crescent",
    category: "Film",
    year: "2024",
    blurb:
      "Forty seconds in the dark: the product appears once, in the final second.",
    image: "assets/hands-sparkler.jpg",
    alt: "Hands lighting a sparkler, final frame of the short film",
    delivered: [
      "Short product film, a single sweep of light",
      "Vertical cut for phone screens",
      "No dialogue, no stock music",
    ],
    result: "The product does not appear until second thirty-nine.",
  },
  {
    id: "katalog-rimba",
    title: "Forest Catalog",
    category: "Website",
    year: "2025",
    blurb:
      "An online catalogue for woodworkers: one page, no cart, no account.",
    image: "assets/hands-spruce.jpg",
    alt: "Two hands holding a spruce shoot, raw material for woodworkers",
    delivered: [
      "Sixty-two work sheets with dimensions and prices",
      "Search without a results page: one list, one filter",
      "Orders by email, not a cart",
    ],
    result: "The woodworkers handle orders from the workshop, not the office.",
  },
  {
    id: "sinyal-pagi",
    title: "Morning Signal",
    category: "AI",
    year: "2025",
    blurb:
      "A newsroom routine that summarises a hundred sources before seven.",
    image: "assets/hands-camera.jpg",
    alt: "Hands holding a rangefinder camera, a newsroom tool",
    delivered: [
      "Summarise-and-check flow with a human reviewer",
      "One news sheet at six in the morning, every day",
      "A source note for every sentence",
    ],
    result: "The newsroom starts from the summary, not a hundred browser tabs.",
  },
];

export interface Service {
  title: string;
  desc: string;
  items: string[];
}

export const services: Service[] = [
  {
    title: "Brand & identity",
    desc: "One mark that outlasts the campaign.",
    items: ["Logogram and mark system", "Palette and typography", "Usage guidelines"],
  },
  {
    title: "Websites & digital products",
    desc: "Pages that open fast and read clearly.",
    items: ["Fast static sites", "Product interfaces", "Content editing"],
  },
  {
    title: "Motion & film",
    desc: "Movement that explains, not decorates.",
    items: ["Short product films", "Vertical cuts", "Interface animation"],
  },
  {
    title: "Content & narrative",
    desc: "Sentences that name the specific, not the adjective.",
    items: ["Copy and headlines", "Photography and layout", "Brand voice"],
  },
  {
    title: "AI & automation",
    desc: "Routines that run without being asked twice.",
    items: ["Summarise-and-check flows", "Search inside documents", "Human review"],
  },
  {
    title: "Wayfinding & space",
    desc: "Signs that work on the street, not only on screen.",
    items: ["Wayfinding systems", "Sound cues", "On-site testing"],
  },
];

export interface Crew {
  name: string;
  role: string;
  tags: string[];
}

export const crew: Crew[] = [
  { name: "Raka Adiwarna", role: "Commander · Strategy", tags: ["@raka", "mail"] },
  { name: "Sella Mahesa", role: "Graphic design · Signage", tags: ["@sella", "print"] },
  { name: "Bimo Hartanto", role: "Web · Technical delivery", tags: ["@bimo", "code"] },
  { name: "Nara Putri", role: "Narrative · Short film", tags: ["@nara", "film"] },
  { name: "Jingga Kalis", role: "Motion · Visual research", tags: ["@jingga", "motion"] },
  { name: "Faris Abdurrahman", role: "AI · Field automation", tags: ["@faris", "flow"] },
];

export const disciplines = [
  "Brand & identity",
  "Website",
  "Motion & film",
  "Content",
  "AI & automation",
  "Wayfinding",
];

export const budgets = ["Not yet decided", "Under 50 million", "50 to 150 million", "Over 150 million"];

export const office = {
  email: "halo@satgas.ai.id",
  phone: "+62 21 5087 5610",
  phoneHref: "tel:+622150875610",
  building: "Antara Building, 3rd floor",
  street: "8 Antara Street, Central Jakarta 10310",
  hours: "Monday to Friday, 09:00 to 18:00 WIB",
  maps: "https://maps.google.com/?q=Jl.+Antara+Jakarta+Pusat",
};
