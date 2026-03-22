# VYBE — AI Restaurant Discovery Platform

VYBE is an AI-powered food discovery and restaurant communication platform. Users find food using natural language and communicate directly with restaurants through an intelligent chat system.

---

## Project Structure

```
vybe/
├── .env
├── main.py
├── db/
│   └── supabase_client.py
├── tools/
│   ├── search_food.py
│   ├── get_nearby.py
│   └── chat_tools.py
└── agents/
    ├── food_discovery_agent.py
    └── chat_agent.py
```

---

## Agents

### Agent 1 — Food Discovery
Handles all food search queries using natural language. Users can search by craving, diet, budget, calories, protein, group size, or location.

**Example queries**
- "I'm craving something cheesy"
- "High protein meals under $20"
- "Vegan food under 500 calories"
- "Food for a party of 20 people"
- "Halal food near me"

**Tools**
| Tool | Purpose |
|---|---|
| `search_food` | Query dishes by price, calories, protein, diet, group size |
| `get_nearby_restaurants` | Find restaurants by location using PostGIS |

---

### Agent 2 — Chat Agent
Handles real-time communication between customers and restaurants. Answers menu questions instantly from DB and routes complex questions to the restaurant with a 60 second auto-reply threshold.

**Decision flow**
```
Customer asks a question
        ↓
Can DB answer this? (spice, allergens, halal, ingredients, menu info)
        ↓
   YES → get_dish_info → reply instantly
   NO  → route to restaurant → wait 60 sec → auto-reply with disclaimer
```

**Tools**
| Tool | Purpose |
|---|---|
| `get_dish_info` | Fetch spice level, allergens, ingredients, halal, vegetarian status |
| `send_message` | Log messages to chat_messages table |
| `check_restaurant_status` | Check if restaurant is currently open |
| `check_pending_reply` | Check if 60 sec threshold exceeded with no restaurant reply |

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq — `llama-3.3-70b-versatile` |
| Agent framework | LangChain + LangGraph |
| Database | Supabase (PostgreSQL) |
| Location queries | PostGIS |
| Memory | LangGraph `InMemorySaver` + Supabase persistence |
| Language | Python 3.11+ |

---

## Setup

### 1. Clone and create environment

```bash
git clone https://github.com/your-repo/vybe-agentic-system
cd vybe-agentic-system
conda create -n ai-agent python=3.11
conda activate ai-agent
```

### 2. Install dependencies

```bash
pip install supabase langchain langchain-groq langchain-core langgraph python-dotenv
```

### 3. Environment variables

Create a `.env` file at the project root:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
GROQ_API_KEY=your-groq-api-key
```

### 4. Database setup

Run these in your Supabase SQL Editor in order:

```sql
-- Enable PostGIS
create extension if not exists postgis;

-- Restaurants table
create table public.restaurants (
  id             uuid primary key default gen_random_uuid(),
  name           text not null,
  category       text not null,
  address        text not null,
  location       geography(point, 4326),
  contact_no     text,
  opening_time   time not null,
  closing_time   time not null,
  website        text,
  instagram      text,
  price_range    text,
  story          text,
  rating         numeric(2,1),
  has_catering   boolean not null default false,
  total_locations int default 1,
  is_halal       boolean not null default false,
  created_at     timestamptz not null default now()
);

-- Food dishes table
create table public.food_dishes (
  id              uuid primary key default gen_random_uuid(),
  restaurant_id   uuid not null references public.restaurants(id) on delete cascade,
  name            text not null,
  category        text,
  description     text,
  spicy_level     int not null default 0 check (spicy_level between 0 and 5),
  calories        numeric(8,2),
  proteins_g      numeric(8,2),
  nutrients       jsonb,
  ingredients     text[] not null default '{}',
  allergens       text[] not null default '{}',
  price           numeric(10,2) not null check (price >= 0),
  is_available    boolean not null default true,
  is_group_item   boolean not null default false,
  is_vegetarian   boolean not null default false,
  is_halal        boolean not null default false,
  created_at      timestamptz not null default now()
);

-- Chat messages table
create table public.chat_messages (
  id                       uuid primary key default gen_random_uuid(),
  thread_id                text not null,
  restaurant_id            uuid references public.restaurants(id),
  role                     text not null check (role in ('user','assistant','customer','restaurant','ai')),
  content                  text not null,
  requires_restaurant_reply boolean default false,
  restaurant_replied_at    timestamptz,
  is_auto_reply            boolean default false,
  created_at               timestamptz not null default now()
);

-- Indexes
create index on public.food_dishes (restaurant_id);
create index on public.chat_messages (thread_id, restaurant_id, created_at desc);
create index on public.restaurants using gist (location);

-- PostGIS nearby function
create or replace function restaurants_nearby(lat float, lng float, radius_meters float default 5000)
returns table (id uuid, name text, category text, address text, opening_time time, closing_time time, distance_meters float)
language sql as $$
  select id, name, category, address, opening_time, closing_time,
    st_distance(location::geography, st_point(lng, lat)::geography) as distance_meters
  from restaurants
  where location is not null
    and st_dwithin(location::geography, st_point(lng, lat)::geography, radius_meters)
  order by distance_meters asc;
$$;
```

### 5. Run

```bash
python main.py
```

---

## Memory Architecture

```
Session starts
      ↓
InMemorySaver — holds conversation within session (fast, in RAM)
      ↓
Every message saved to Supabase chat_messages (persistent across restarts)
      ↓
On new session — last 10 messages loaded from Supabase into context
```

---


## Roadmap

- [ ] Agent 2 full test coverage (TEST 2, 4, 5)
- [ ] Populate PostGIS location data for all restaurants
- [ ] Long-term user preference memory (v2)
- [ ] Single entry point connecting both agents
- [ ] Frontend chat UI
- [ ] Order placement integration

---

## Rate Limits

This project uses Groq's free developer tier with the following limits for `llama-3.3-70b-versatile`:

- 100,000 tokens per day
- 300,000 tokens per minute
- 1,000 requests per minute

If you hit the daily limit, either wait 24 hours or upgrade to Groq Dev Tier at console.groq.com/settings/billing.

---

