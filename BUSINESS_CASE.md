# Umamimatch: Business Case & Product Vision

## 1. Core Concept: Effortless, Masked Group Decisions
Umamimatch is a gamified, agent-driven platform designed to solve the classic "where should we eat?" problem for groups of friends or colleagues. 

The core value proposition is **effortless group matching based on masked individual preferences**. The system securely holds each user's true preferences (allergies, diet, budget, hidden dislikes) without disclosing them directly to the group. It then calculates the optimal shared decision, ensuring everyone is happy while avoiding awkward social friction or public vetoes.

The system revolves around **user “bases”** (e.g., home, work, or other frequent locations). Users define **distance preferences** relative to these anchor points, creating the geographical foundation for all smart recommendations and group matching.

---

## 2. Gamified Profiling: Fun Input, Private Output
To gather the deep data needed for optimal group matching, Umamimatch moves away from boring, static forms toward a **cool, expressive profiling system**.

* **Smart Assumptions & Feedback Loops:** The system actively makes assumptions about a user's preferences based on their activity. Users can confirm or override these assumptions using natural language, creating a light, game-like interaction that encourages continuous engagement.
* **Masked by Default:** The rich, structured persona data collected through this playful UX is kept strictly private. The agent uses it to rank options for the group, but individual sensitivities are never exposed on the dashboard.

---

## 3. Product Vision: The Dashboard as a Central Hub
The Umamimatch experience is anchored by a **visually engaging, map-centric interactive dashboard** that brings the group ecosystem together. 

* **Map-First Visualization:** Maps are central to the experience, not secondary. The dashboard visually plots user bases, candidate restaurants, and highlights the optimal choice for the assembled group.
* **Exploratory & Dynamic:** The dashboard highlights top recommendations and team preference insights in an exploratory way, focusing on the shared outcome rather than individual constraints.
* **Decision Support:** The decision-making component is integrated directly into the dashboard to rank restaurants, compare options, and definitively present the absolute best choices for the group.

---

## 4. Agent-Driven Background Infrastructure
The heavy lifting of the platform happens seamlessly behind the scenes, keeping the frontend clean, fast, and focused on the group outcome.

* **Agentic Execution:** Core logic—including scraping updates, recommendations, and the masked preference matching algorithm—is driven by autonomous background AI agents (leveraging our LangGraph foundation).
* **Background Scraping:** A lightweight, efficient scraper connected to Google Maps restaurant data runs asynchronously. It prioritizes efficiency over complexity.
* **Smart Caching:** The system heavily utilizes caching to store favorite restaurants and avoid repeated, expensive data fetching during rapid group decisions.

---

## 5. Social Layer & Community Discovery (Future Horizon)
While the core is solving immediate group decisions, Umamimatch naturally extends into broader connection.

* **Group & Match Discovery:** As a secondary feature, the system can recommend potential existing groups to join or similar/complementary users who share the same location bases.
* **Diverse Perspectives:** The matching algorithm is designed to enable the discovery of like-minded people as well as introduce diverse matches (different perspectives, same location) to foster a vibrant local community.

---

## 6. Alignment with Current Repository Capabilities
We are building Umamimatch on top of our existing, clean codebase. This pivot heavily reuses our current strengths while shifting the UX focus toward masked group decisions:

* **FastAPI & SQLite Foundation:** Provides the fast, reliable backend and structured data models needed for secure user profiles, bases, and caching.
* **LangGraph Agent Flow:** Our existing decision agent and LLM factory (OpenAI/Vertex) are perfectly positioned to act as the neutral arbiter that computes the optimal group choice from masked preferences.
* **Next.js & Tailwind UI:** The clean design system will be upgraded to feature the interactive, map-centric dashboard and gamified profiling UI elements.
* **Scraping Architecture:** The existing orchestrator/strategy seam easily integrates lightweight Google Maps scraping and background caching without cluttering the main app flow.

*Our goal: A cool, interactive, gamified experience powered by an intelligent agent that solves group decisions effortlessly while keeping individual preferences private.*