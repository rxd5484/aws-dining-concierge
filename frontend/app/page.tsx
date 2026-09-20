"use client";

import { FormEvent, useMemo, useState } from "react";

type Recommendation = {
  name: string;
  cuisine: string;
  location: string;
  rating: number;
  address: string;
};

type FormState = {
  location: string;
  cuisine: string;
  date: string;
  time: string;
  party_size: number;
  email: string;
};

const cuisines = [
  "American",
  "Chinese",
  "French",
  "Greek",
  "Indian",
  "Italian",
  "Japanese",
  "Korean",
  "Mediterranean",
  "Mexican",
  "Thai",
  "Vietnamese",
];

const demoRestaurants: Recommendation[] = [
  { name: "Saffron House", cuisine: "Indian", location: "Manhattan", rating: 4.8, address: "118 Lexington Ave, New York, NY" },
  { name: "Curry Leaf Brooklyn", cuisine: "Indian", location: "Brooklyn", rating: 4.6, address: "73 Atlantic Ave, Brooklyn, NY" },
  { name: "Tokyo Alley", cuisine: "Japanese", location: "Manhattan", rating: 4.7, address: "14 E 13th St, New York, NY" },
  { name: "Sushi Harbor", cuisine: "Japanese", location: "Brooklyn", rating: 4.5, address: "215 Court St, Brooklyn, NY" },
  { name: "Casa Verde", cuisine: "Mexican", location: "Queens", rating: 4.7, address: "31-18 30th Ave, Astoria, NY" },
  { name: "Nonna's Corner", cuisine: "Italian", location: "Manhattan", rating: 4.6, address: "83 Thompson St, New York, NY" },
  { name: "Basil & Stone", cuisine: "Mediterranean", location: "Brooklyn", rating: 4.8, address: "190 Bedford Ave, Brooklyn, NY" },
  { name: "Bangkok Night Market", cuisine: "Thai", location: "Queens", rating: 4.6, address: "71-22 Roosevelt Ave, Jackson Heights, NY" },
  { name: "Seoul Kitchen", cuisine: "Korean", location: "Manhattan", rating: 4.8, address: "12 W 32nd St, New York, NY" },
  { name: "Juniper Table", cuisine: "American", location: "Manhattan", rating: 4.7, address: "21 W 18th St, New York, NY" }
];

const apiUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

export default function Home() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [form, setForm] = useState<FormState>({
    location: "Manhattan",
    cuisine: "Indian",
    date: today,
    time: "19:00",
    party_size: 2,
    email: "",
  });
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const [results, setResults] = useState<Recommendation[]>([]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function runDemo() {
    await new Promise((resolve) => setTimeout(resolve, 900));
    const sameCuisine = demoRestaurants.filter((r) => r.cuisine === form.cuisine);
    const picks = (sameCuisine.length ? sameCuisine : demoRestaurants).slice(0, 3);
    setResults(picks);
    setMessage("Demo mode: recommendations generated locally. Connect the AWS API to enable the full asynchronous workflow and SES email delivery.");
    setStatus("done");
  }

  async function poll(requestId: string) {
    for (let attempt = 0; attempt < 18; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const response = await fetch(`${apiUrl}/requests/${requestId}`);
      const data = await response.json();

      if (!response.ok) throw new Error(data.error || "Could not read request status.");
      if (data.status === "COMPLETED") {
        setResults(data.recommendations || []);
        setMessage(data.email_sent ? "Recommendations are ready and were emailed to you." : "Recommendations are ready. SES email is disabled or not yet configured.");
        setStatus("done");
        return;
      }
      if (data.status === "FAILED" || data.status === "FAILED_TO_QUEUE") {
        throw new Error(data.error || "The recommendation job failed.");
      }
    }
    throw new Error("The request is still processing. Try again in a moment.");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("loading");
    setResults([]);
    setMessage("");

    try {
      if (!apiUrl) {
        await runDemo();
        return;
      }

      const response = await fetch(`${apiUrl}/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not submit dining request.");
      setMessage("Request queued. EventBridge and SQS are processing it now…");
      await poll(data.request_id);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Something went wrong.");
    }
  }

  return (
    <main>
      <section className="hero">
        <div className="eyebrow">SERVERLESS · EVENT-DRIVEN · AWS</div>
        <h1>Dining Concierge</h1>
        <p className="subtitle">
          Tell us where and what you want to eat. The app queues your request, finds matching restaurants, stores the result, and can email the recommendations.
        </p>
        <div className="architecture">
          <span>Next.js</span><b>→</b><span>API Gateway</span><b>→</b><span>Lambda</span><b>→</b><span>EventBridge</span><b>→</b><span>SQS</span><b>→</b><span>Lambda</span><b>→</b><span>DynamoDB / OpenSearch / SES</span>
        </div>
      </section>

      <section className="panel-grid">
        <form className="card form-card" onSubmit={submit}>
          <div className="section-kicker">REQUEST</div>
          <h2>Plan dinner</h2>

          <label>
            Location
            <select value={form.location} onChange={(e) => update("location", e.target.value)}>
              <option>Manhattan</option><option>Brooklyn</option><option>Queens</option><option>New York City</option>
            </select>
          </label>

          <label>
            Cuisine
            <select value={form.cuisine} onChange={(e) => update("cuisine", e.target.value)}>
              {cuisines.map((cuisine) => <option key={cuisine}>{cuisine}</option>)}
            </select>
          </label>

          <div className="split">
            <label>
              Date
              <input type="date" min={today} value={form.date} onChange={(e) => update("date", e.target.value)} required />
            </label>
            <label>
              Time
              <input type="time" value={form.time} onChange={(e) => update("time", e.target.value)} required />
            </label>
          </div>

          <label>
            Party size
            <input type="number" min="1" max="20" value={form.party_size} onChange={(e) => update("party_size", Number(e.target.value))} required />
          </label>

          <label>
            Email
            <input type="email" placeholder="you@example.com" value={form.email} onChange={(e) => update("email", e.target.value)} required />
          </label>

          <button disabled={status === "loading"} type="submit">
            {status === "loading" ? "Finding restaurants…" : "Get recommendations"}
          </button>
          <p className="mode">{apiUrl ? "AWS backend connected" : "Portfolio demo mode — AWS API not configured"}</p>
        </form>

        <section className="card results-card">
          <div className="section-kicker">RESULTS</div>
          <h2>Your recommendations</h2>
          {status === "idle" && <p className="muted">Submit a request to see restaurant suggestions.</p>}
          {status === "loading" && <div className="loader"><span /><span /><span /></div>}
          {message && <p className={status === "error" ? "message error" : "message"}>{message}</p>}

          <div className="results-list">
            {results.map((restaurant, index) => (
              <article className="restaurant" key={`${restaurant.name}-${index}`}>
                <div className="rank">0{index + 1}</div>
                <div>
                  <h3>{restaurant.name}</h3>
                  <p>{restaurant.cuisine} · {restaurant.location}</p>
                  <p className="address">{restaurant.address}</p>
                </div>
                <div className="rating">★ {restaurant.rating}</div>
              </article>
            ))}
          </div>
        </section>
      </section>

      <footer>
        <span>Built with Next.js + AWS serverless services</span>
        <span>Designed for Vercel + AWS SAM deployment</span>
      </footer>
    </main>
  );
}
