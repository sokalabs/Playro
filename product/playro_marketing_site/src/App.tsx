import { Bot, Code2, Rocket, Sparkles, CheckCircle2, MonitorPlay } from 'lucide-react';

function App() {
  const REPO_URL = "https://github.com/sokalabs/Hermes-Roblox";

  return (
    <div className="min-h-screen font-sans selection:bg-primary/30">
      {/* Navigation */}
      <nav className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
            <MonitorPlay className="w-6 h-6 text-primary" />
            Playro
          </div>
          <div className="flex items-center gap-6 text-sm font-medium">
            <a href="#features" className="text-slate-400 hover:text-white transition-colors">Features</a>
            <a href="#download" className="text-slate-400 hover:text-white transition-colors">Download</a>
            <a href={REPO_URL} className="bg-primary hover:bg-primary-hover text-white px-4 py-2 rounded-lg transition-colors">
              View on GitHub
            </a>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <main>
        <section className="pt-32 pb-20 px-6 text-center max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium mb-8 border border-primary/20">
            <Sparkles className="w-4 h-4" />
            Public prototype for Roblox creators
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-8 leading-tight">
            Build Roblox games from a <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-blue-400">text prompt.</span>
          </h1>
          <p className="text-lg md:text-xl text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed">
            Playro is an AI-powered desktop app that turns your ideas into playable Roblox Studio projects. No coding required—just describe the game you want.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              href={REPO_URL}
              className="w-full sm:w-auto bg-primary hover:bg-primary-hover text-white text-lg font-semibold px-8 py-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:-translate-y-0.5"
            >
              <Rocket className="w-5 h-5" />
              Get the source
            </a>
            <a
              href="#demo"
              className="w-full sm:w-auto bg-slate-800 hover:bg-slate-700 text-white text-lg font-semibold px-8 py-4 rounded-xl transition-all"
            >
              See how it works
            </a>
          </div>
          <p className="mt-6 text-sm text-slate-500">Requires Windows 10/11 and Roblox Studio.</p>
        </section>

        {/* Feature Grid */}
        <section id="features" className="py-24 bg-slate-900 border-y border-slate-800">
          <div className="max-w-6xl mx-auto px-6">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold mb-4">From idea to playtesting in minutes.</h2>
              <p className="text-slate-400 max-w-xl mx-auto">Stop fighting the Luau API. Let Playro scaffold your mechanics, server logic, and client UI automatically.</p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              <div className="bg-slate-950 p-8 rounded-2xl border border-slate-800">
                <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center mb-6">
                  <Bot className="w-6 h-6 text-blue-400" />
                </div>
                <h3 className="text-xl font-bold mb-3">AI Orchestration</h3>
                <p className="text-slate-400 leading-relaxed">Powered by the Hermes AI framework, Playro plans the architecture, writes the code, and verifies the syntax before handing it off to you.</p>
              </div>

              <div className="bg-slate-950 p-8 rounded-2xl border border-slate-800">
                <div className="w-12 h-12 bg-purple-500/10 rounded-xl flex items-center justify-center mb-6">
                  <Code2 className="w-6 h-6 text-purple-400" />
                </div>
                <h3 className="text-xl font-bold mb-3">Native Rojo Projects</h3>
                <p className="text-slate-400 leading-relaxed">Playro generates standard Rojo project structures (`default.project.json`). It integrates perfectly with your existing Roblox Studio workflow.</p>
              </div>

              <div className="bg-slate-950 p-8 rounded-2xl border border-slate-800">
                <div className="w-12 h-12 bg-emerald-500/10 rounded-xl flex items-center justify-center mb-6">
                  <MonitorPlay className="w-6 h-6 text-emerald-400" />
                </div>
                <h3 className="text-xl font-bold mb-3">Desktop First</h3>
                <p className="text-slate-400 leading-relaxed">A native Windows desktop app that runs locally. No browser tabs. Just type your prompt and watch the build progress in real-time.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Download / CTA */}
        <section id="download" className="py-32 px-6">
          <div className="max-w-4xl mx-auto bg-gradient-to-b from-slate-800 to-slate-900 rounded-3xl p-1 border border-slate-700 shadow-2xl">
            <div className="bg-slate-950 rounded-[22px] p-8 md:p-12 text-center relative overflow-hidden">
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-1/2 bg-primary/10 blur-[100px] pointer-events-none"></div>

              <h2 className="text-3xl md:text-4xl font-bold mb-4 relative">Start building today.</h2>
              <p className="text-slate-400 mb-10 text-lg relative">Clone the project, run the desktop prototype, and help shape the Roblox builder roadmap.</p>

              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-8 max-w-sm mx-auto mb-10 relative backdrop-blur-sm">
                <div className="text-5xl font-extrabold mb-2">MIT</div>
                <div className="text-sm text-slate-400 mb-6 uppercase tracking-wider font-semibold">Open source license</div>

                <ul className="text-left space-y-4 mb-8">
                  <li className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-primary shrink-0" />
                    <span className="text-slate-300">Playro desktop source code</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-primary shrink-0" />
                    <span className="text-slate-300">No-key local smoke generation</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-primary shrink-0" />
                    <span className="text-slate-300">Community contributions welcome</span>
                  </li>
                </ul>

                <a
                  href={REPO_URL}
                  className="block w-full bg-primary hover:bg-primary-hover text-white font-bold py-4 rounded-xl transition-colors"
                >
                  View Repository
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 py-12 text-center text-slate-500">
        <p className="mb-2">© 2026 SokaLabs. Released under the MIT License.</p>
        <p className="text-sm">Not affiliated with Roblox Corporation.</p>
      </footer>
    </div>
  );
}

export default App;
