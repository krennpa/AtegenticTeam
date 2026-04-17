# Umamimatch: Business Case & Product Vision

## 1. Core Concept
Umamimatch is a gamified, agent-driven platform designed to make finding food and community effortless and fun. 

The system revolves around **user “bases”** (e.g., home, work, or other frequent locations). Users define **distance preferences** relative to these anchor points, and these bases act as the foundation for all smart recommendations and decision-making in the app.

---

## 2. Product Vision: The Dashboard as a Central Hub
The core of the Umamimatch experience is a **visually engaging, map-centric interactive dashboard** that brings the entire ecosystem together. 

* **Map-First Visualization:** Maps are central to the experience, not secondary. The dashboard visually plots user bases, candidate restaurants, and selected choices.
* **Exploratory & Dynamic:** The dashboard highlights top recommendations, ranked restaurant options, and user preference insights in a playful, exploratory way.
* **Decision Support:** A clear decision-making component is integrated directly into the dashboard to rank restaurants, compare options, and highlight the absolute best choices for the user or group.

---

## 3. Gamified Profiling & Personalization
Umamimatch moves away from boring, static forms toward a **cool, expressive profiling system**.

* **Structured Persona Data:** We maintain a unique, structured data format for persona characteristics, distance preferences, food tastes, and behavioral patterns.
* **Smart Assumptions & Feedback Loops:** The system actively makes assumptions about a user's preferences based on their activity. Users can confirm or override these assumptions using natural language, creating a light, game-like interaction that encourages continuous engagement.

---

## 4. Agent-Driven Background Infrastructure
The heavy lifting of the platform happens seamlessly behind the scenes, keeping the frontend clean and fast.

* **Background Scraping:** A lightweight, efficient scraper connected to Google Maps restaurant data runs asynchronously. It prioritizes efficiency over complexity.
* **Smart Caching:** The system heavily utilizes caching to store favorite restaurants and avoid repeated, expensive data fetching.
* **Agentic Execution:** Core logic—including scraping updates, recommendations, and matching—is driven by autonomous background AI agents (leveraging our LangGraph foundation).

---

## 5. Social Layer & Community Discovery
Umamimatch recommends more than just food; it recommends connection.

* **Group & Match Discovery:** The system recommends potential groups to join or similar/complementary users who share the same location bases.
* **Diverse Perspectives:** The matching algorithm is designed to enable the discovery of like-minded people as well as introduce diverse matches (different perspectives, same location) to foster a vibrant local community.

---

## 6. Alignment with Current Repository Capabilities
We are building Umamimatch on top of our existing, clean codebase. This pivot heavily reuses our current strengths while shifting the UX focus:

* **FastAPI & SQLite Foundation:** Provides the fast, reliable backend and structured data models needed for user bases and caching.
* **LangGraph Agent Flow:** Our existing decision agent and LLM factory (OpenAI/Vertex) will be expanded to drive the background "assumptions" engine and smart restaurant ranking.
* **Next.js & Tailwind UI:** The clean design system will be upgraded to feature the interactive, map-centric dashboard and gamified UI elements.
* **Scraping Architecture:** The existing orchestrator/strategy seam is perfectly positioned to integrate lightweight Google Maps scraping and background caching without cluttering the main app flow.

*Our goal: A cool, interactive, gamified experience powered by simple but smart agentic infrastructure running behind the scenes.*