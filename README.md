# Portfolio Copilot

Portfolio Copilot is a personal finance and investing assistant that
plans its own next move.

Instead of following a fixed script, a single agent looks at your goal,
checks what it's currently allowed to do, and decides for itself how to
get there, pulling in research, checking your portfolio, and drafting a
trade if one's warranted. Nothing happens with your money without your
sign-off, and every decision it makes is traceable back to exactly which
capability made it, and why.

## Why try it

- **It plans, it doesn't run a script.** Ask it something and watch it
  work out, in the moment, what it needs to check and do. It's not a
  hardcoded pipeline of steps that runs the same way every time.
- **You can revoke what it's allowed to do, live, mid-conversation**,
  and watch it adapt on the very next step. No restart, no error.
- **Nothing happens with your money without you approving it first.**
  Proposed trades are drafted, checked against your own stated
  investment policy, and only ever executed after you say yes.
- **It's a real demonstration of agent governance**, not a slide about
  it. Every action is traceable to the exact skill, version, and
  approval that authorized it.

This is a personal project and demo, built on Google Cloud's Gemini
Enterprise Agent Platform. It's not a product, not investment advice,
and not connected to a real brokerage (trades run through Alpaca's
paper trading API).

## Get started

Setup instructions: [`install/`](install/).

## How to use it

*This section is a placeholder. There's no frontend yet, so nothing
below is real usage documentation, it's a sketch of the intended flow
so the eventual UI has a clear target rather than being designed from
scratch. Replace this whole section once `frontend/` exists.*

### First time: onboarding

You'll answer a short interview: your goals, time horizon, how you'd
react to a market drop, what you're carrying in debt. From that, the
agent builds your Investment Policy Statement, the reference plan
everything else checks against.

### Day to day: checking in

Ask it how your spending looks, whether your portfolio has drifted from
target, or what's going on with a specific holding. It answers using
live data, not a cached summary.

### When it wants to act: approving a trade

If it thinks a trade is warranted, it drafts a specific proposal, ticker,
quantity, and rationale, checks it against your policy, and shows you
exactly what it wants to do before anything happens. Nothing executes
without your yes.

## Learn more

- **Component Documentation**:
  - [`orchestrator/README.md`](orchestrator/README.md): Python ADK root planner & dynamic planning workflow
  - [`frontend/README.md`](frontend/README.md): Standalone Vue 3 + TypeScript SPA & Stitch design system
  - [`gateway/README.md`](gateway/README.md): Go API Gateway microservice (F7 contract)
- **Specifications & Architecture**: see [`docs/spec/`](docs/spec/) and [`docs/adr/`](docs/adr/).
- **Contributor / Coding-Agent Instructions**: see [`AGENTS.md`](AGENTS.md).

## Status

Foundation, orchestrator skills, Go API Gateway, and standalone Vue 3 frontend implemented. See [`docs/adr/`](docs/adr/) for the current state of each major decision.

## Built With

This application was built with the assistance of
[Stitch](https://stitch.withgoogle.com/) and [Jules](https://jules.google.com).

## Contributing

Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for details on how to
contribute to this project.

## Support

This demo is *NOT* endorsed by Google or Google Cloud. The repo is
intended for educational/hobbyist use only.

## License

This project is licensed under the terms of the [LICENSE](./LICENSE) file.
