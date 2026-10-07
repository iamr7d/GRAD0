"""Pick a literal stock-footage search for a story when no LLM is available.

Headlines are full of figurative words ("questions swirling", "storm over", "battle for")
that make stock search return abstract art. We look for concrete news topics instead,
and fall back to a safe, literal shot for the story's category.
"""
import re

# topic words -> literal footage that a stock library actually has
TOPICS = [
    (r"\b(police|arrest|arrested|detain|crime|murder|stabbing|shooting|suspect|court|trial|judge|prison)\b", "police officers city street"),
    (r"\b(military|army|troops|soldier|air ?base|airbase|base|missile|drone|strike|attack|war|navy|defence|defense)\b", "military aircraft airbase"),
    (r"\b(protest|protests|protester|riot|tear gas|demonstrat\w*|march|strike action)\b", "protest crowd street"),
    (r"\b(election|vote|voters|ballot|parliament|congress|senate|minister|president|government|policy|law)\b", "government building flags"),
    (r"\b(fire|wildfire|blaze|burn\w*)\b", "fire firefighters smoke"),
    (r"\b(flood|floods|storm|hurricane|cyclone|typhoon|rain)\b", "flood storm rain"),
    (r"\b(earthquake|quake|tsunami|landslide)\b", "earthquake damage rubble"),
    (r"\b(climate|emission\w*|carbon|heatwave|drought)\b", "climate change industry smoke"),
    (r"\b(market|stocks?|shares|economy|inflation|bank|interest rate|imf|rupee|dollar|trade|tariff\w*)\b", "stock market trading screen"),
    (r"\b(oil|gas|energy|nuclear|power plant|solar|wind farm|battery)\b", "power plant energy"),
    (r"\b(ai|artificial intelligence|openai|chatbot|robot\w*)\b", "artificial intelligence technology"),
    (r"\b(apple|google|microsoft|amazon|meta|tesla|iphone|smartphone|app|software|tech)\b", "technology office computer"),
    (r"\b(game|gaming|xbox|playstation|nintendo|gta)\b", "video game controller"),
    (r"\b(space|nasa|rocket|satellite|moon|mars)\b", "rocket launch space"),
    (r"\b(health|hospital|doctor|virus|vaccine|disease|cancer|medical)\b", "hospital doctors medical"),
    (r"\b(school|students?|university|education)\b", "students school classroom"),
    (r"\b(football|cricket|tennis|olympic\w*|match|tournament|league)\b", "stadium sports crowd"),
    (r"\b(film|movie|music|concert|actor|singer|comedian|comic\w*|festival)\b", "concert stage lights"),
    (r"\b(airline|flight|airport|plane)\b", "airport airplane"),
    (r"\b(train|rail|railway)\b", "train railway"),
    (r"\b(ship|shipping|port|vessel\w*|tanker)\b", "cargo ship port"),
    (r"\b(refugee\w*|migrant\w*|border)\b", "border fence migrants"),
    (r"\b(gaza|israel|ukraine|russia|iran|syria|lebanon)\b", "war conflict city damage"),
]
CATEGORY = {"World": "world news city skyline", "Business": "stock market trading screen",
            "Tech": "technology office computer", "Science": "science laboratory research",
            "India": "india city street traffic"}


def search_terms(title, summary="", category="World"):
    """Return search queries to try, most specific first."""
    text = f"{title} {summary}".lower()
    hits = [q for pat, q in TOPICS if re.search(pat, text)]
    out = list(dict.fromkeys(hits[:2]))          # at most two topic queries, in order of appearance
    out.append(CATEGORY.get(category, "world news city skyline"))
    return out


if __name__ == "__main__":
    print(search_terms("The questions swirling around a U.K. base and possible Iranian-backed attacks",
                       "British police said they had made a seventh arrest", "World"))
