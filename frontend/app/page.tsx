"use client"

import Link from 'next/link'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card'
import { Users, FilePlus2, Bot, Github, ArrowRight, Sparkles, LogOut } from 'lucide-react'
import { motion } from 'framer-motion'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog'
import { AuthForm } from '../components/forms/AuthForm'
import { useAuth } from '../lib/auth-context'
import { Avatar, AvatarFallback } from '../components/ui/avatar'

export default function Page() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="text-2xl font-bold text-slate-900">Dynalunch</div>
            <nav className="hidden md:flex items-center gap-8">
              <Link href="#features" className="text-slate-600 hover:text-slate-900 transition-colors">Features</Link>
              <Link href="#how-it-works" className="text-slate-600 hover:text-slate-900 transition-colors">How it works</Link>
              {user ? (
                <>
                  <Link href="/dashboard">
                    <Button variant="ghost" className="rounded-xl">Dashboard</Button>
                  </Link>
                  <Link href="/teams">
                    <Button variant="ghost" className="rounded-xl">Teams</Button>
                  </Link>
                  <div className="flex items-center gap-2">
                    <Link href="/profile">
                      <Avatar className="h-8 w-8 cursor-pointer hover:opacity-80 transition-opacity">
                        <AvatarFallback className="text-xs">
                          {user.displayName?.charAt(0)?.toUpperCase() || user.email?.charAt(0)?.toUpperCase() || 'U'}
                        </AvatarFallback>
                      </Avatar>
                    </Link>
                    <Button variant="ghost" size="icon" onClick={logout} className="rounded-xl">
                      <LogOut className="h-4 w-4" />
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <Dialog>
                    <DialogTrigger asChild>
                      <Button variant="ghost" className="rounded-xl">Login</Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Welcome back</DialogTitle>
                      </DialogHeader>
                      <AuthForm mode="login" />
                    </DialogContent>
                  </Dialog>
                  <Dialog>
                    <DialogTrigger asChild>
                      <Button className="rounded-xl">Get Started</Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create your account</DialogTitle>
                      </DialogHeader>
                      <AuthForm mode="signup" />
                    </DialogContent>
                  </Dialog>
                </>
              )}
            </nav>
          </div>
        </div>
      </header>

      {/* Hero - Full Width */}
      <section className="relative py-32 text-center overflow-hidden">
        {/* Background Image */}
        <div className="absolute inset-0 z-0">
          <img 
            src="/aestetics/nathan-anderson.jpg" 
            alt="Hero background" 
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-br from-slate-900/70 via-slate-800/60 to-slate-900/80"></div>
        </div>
        
        {/* Content */}
        <div className="container mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="relative z-10 space-y-8"
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/20 backdrop-blur-sm border border-blue-400/30 text-blue-100 text-sm font-medium">
              <Sparkles className="h-4 w-4" />
              AI-Powered Decision Making
            </div>
            <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-white">
              Make Group Lunch<br />Decisions Effortless
            </h1>
            <p className="text-xl text-slate-200 max-w-3xl mx-auto leading-relaxed">
              Form a team, add restaurant menus, and let AI choose the perfect fit for everyone. 
              Privacy-first, intelligent, and beautifully simple.
            </p>
            <div className="flex flex-wrap gap-4 justify-center pt-4">
              <Dialog>
                <DialogTrigger asChild>
                  <Button size="lg" className="rounded-xl px-8 py-3 text-base bg-blue-600 hover:bg-blue-700 text-white shadow-lg">
                    Start Free Today
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Create your account</DialogTitle>
                  </DialogHeader>
                  <AuthForm mode="signup" />
                </DialogContent>
              </Dialog>
              <Link href="/teams">
                <Button variant="outline" size="lg" className="rounded-xl px-8 py-3 text-base border-white/30 text-white hover:bg-white/10 backdrop-blur-sm">
                  View Demo
                </Button>
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      <main className="container mx-auto px-6">

        {/* How it works */}
        <section id="how-it-works" className="py-20">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-center space-y-12"
          >
            <h2 className="text-4xl font-bold text-slate-900">How It Works</h2>
            <div className="grid md:grid-cols-3 gap-8">
              <Card className="border-0 shadow-lg hover:shadow-xl transition-shadow duration-300">
                <CardHeader className="text-center pb-4">
                  <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mx-auto mb-4">
                    <Users className="h-6 w-6 text-[#3a8aca]" />
                  </div>
                  <CardTitle className="text-xl">Join a Team</CardTitle>
                  <CardDescription>Invite friends or colleagues</CardDescription>
                </CardHeader>
                <CardContent className="text-center">
                  Create or join a team to collaborate privately. Only membership is visible, never individual preferences.
                </CardContent>
              </Card>
              <Card className="border-0 shadow-lg hover:shadow-xl transition-shadow duration-300">
                <CardHeader className="text-center pb-4">
                  <div className="w-12 h-12 bg-green-50 rounded-xl flex items-center justify-center mx-auto mb-4">
                    <FilePlus2 className="h-6 w-6 text-[#c8d643]" />
                  </div>
                  <CardTitle className="text-xl">Add Menus</CardTitle>
                  <CardDescription>Paste links to restaurant menus</CardDescription>
                </CardHeader>
                <CardContent className="text-center">
                  Paste menu URLs. We scrape and store raw markdown for accurate context later.
                </CardContent>
              </Card>
              <Card className="border-0 shadow-lg hover:shadow-xl transition-shadow duration-300">
                <CardHeader className="text-center pb-4">
                  <div className="w-12 h-12 bg-purple-50 rounded-xl flex items-center justify-center mx-auto mb-4">
                    <Bot className="h-6 w-6 text-[#63308c]" />
                  </div>
                  <CardTitle className="text-xl">Get a Decision</CardTitle>
                  <CardDescription>AI makes the call, with reasoning</CardDescription>
                </CardHeader>
                <CardContent className="text-center">
                  Our agent considers the team's needs and the menus to recommend one restaurant and dish — with transparent reasoning.
                </CardContent>
              </Card>
            </div>
          </motion.div>
        </section>

        {/* Features */}
        <section id="features" className="py-20 bg-slate-50 -mx-6 px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="text-center space-y-12"
          >
            <h2 className="text-4xl font-bold text-slate-900">Why Choose Dynalunch</h2>
            <div className="grid md:grid-cols-3 gap-8">
              <div className="text-center space-y-4">
                <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto">
                  <div className="w-8 h-8 bg-[#3a8aca] rounded-lg"></div>
                </div>
                <h3 className="text-xl font-semibold text-slate-900">Privacy-first</h3>
                <p className="text-slate-600">Profiles remain private. Decisions are made collectively, and only membership is visible to teammates.</p>
              </div>
              <div className="text-center space-y-4">
                <div className="w-16 h-16 bg-green-50 rounded-2xl flex items-center justify-center mx-auto">
                  <div className="w-8 h-8 bg-[#c8d643] rounded-lg"></div>
                </div>
                <h3 className="text-xl font-semibold text-slate-900">AI-powered</h3>
                <p className="text-slate-600">Uses raw scraped markdown to understand menus and match them to your team's needs.</p>
              </div>
              <div className="text-center space-y-4">
                <div className="w-16 h-16 bg-purple-50 rounded-2xl flex items-center justify-center mx-auto">
                  <div className="w-8 h-8 bg-[#63308c] rounded-lg"></div>
                </div>
                <h3 className="text-xl font-semibold text-slate-900">Smooth workflows</h3>
                <p className="text-slate-600">Create teams, add menus, and decide — all in a few clicks.</p>
              </div>
            </div>
          </motion.div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t bg-white py-12">
        <div className="container mx-auto px-6">
          <div className="flex items-center justify-center gap-8 text-slate-500">
            <Link className="hover:text-slate-700 transition-colors" href="#">About</Link>
            <Link className="hover:text-slate-700 transition-colors" href="#">Contact</Link>
            <a className="inline-flex items-center gap-2 hover:text-slate-700 transition-colors" href="https://github.com/" target="_blank" rel="noreferrer">
              <Github className="h-4 w-4" /> GitHub
            </a>
          </div>
          <div className="text-center text-slate-400 text-sm mt-8">
            © 2024 Dynalunch. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  )
}
