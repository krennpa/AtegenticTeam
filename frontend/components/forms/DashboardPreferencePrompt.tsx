'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import { usePreferenceGame } from '../../lib/use-preference-game'
import { PreferenceQuestion } from '../../lib/types'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'

function prettyToken(value: string): string {
  return value
    .replace(/[_:]/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function getOptionClass(eventType: PreferenceQuestion['eventType']): string {
  if (eventType === 'veto_card') {
    return 'border-red-200 bg-red-50 text-red-800 hover:bg-red-100'
  }
  if (eventType === 'slider') {
    return 'border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100'
  }
  return 'border-sky-200 bg-sky-50 text-sky-900 hover:bg-sky-100'
}

export function DashboardPreferencePrompt() {
  const [seenQuestionKeys, setSeenQuestionKeys] = useState<string[]>([])
  const { progress, questions, loading, submittingKey, error, notice, submitAnswer } = usePreferenceGame({
    questionLimit: 5,
  })

  useEffect(() => {
    if (questions.length === 0) {
      setSeenQuestionKeys([])
      return
    }
    const hasUnseen = questions.some((question) => !seenQuestionKeys.includes(question.questionKey))
    if (!hasUnseen) {
      setSeenQuestionKeys([])
    }
  }, [questions, seenQuestionKeys])

  const question = useMemo(
    () => questions.find((entry) => !seenQuestionKeys.includes(entry.questionKey)) ?? questions[0],
    [questions, seenQuestionKeys]
  )

  const onAnswer = async (answer: string) => {
    if (!question) return
    const answeredKey = question.questionKey
    setSeenQuestionKeys((previous) =>
      previous.includes(answeredKey) ? previous : [...previous, answeredKey]
    )
    const success = await submitAnswer(question, answer, {
      successMessage: 'Saved. Ready for the next prompt.',
    })
    if (!success) {
      setSeenQuestionKeys((previous) => previous.filter((key) => key !== answeredKey))
    }
  }

  return (
    <Card className="overflow-hidden border-sky-200/70 bg-gradient-to-br from-sky-50 via-white to-emerald-50">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-slate-900">
              <Sparkles className="h-5 w-5 text-sky-600" />
              Quick Preference Check
            </CardTitle>
            <CardDescription>
              Answer one prompt to keep your profile fresh.
            </CardDescription>
            <p className="mt-1 text-xs text-slate-500">
              Examples: cuisine pairing, spice level, lunch pace.
            </p>
          </div>
          {progress && (
            <div className="rounded-full border border-sky-200 bg-white px-3 py-1 text-xs text-slate-700">
              L{progress.level} - {progress.points} pts
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading && <p className="text-sm text-slate-600">Loading your next prompt...</p>}

        {error && (
          <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}

        {notice && (
          <p className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            {notice}
          </p>
        )}

        {!loading && question ? (
          <motion.div
            key={question.questionKey}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="rounded-xl border border-slate-200 bg-white p-4"
          >
            <div className="mb-2 flex flex-wrap gap-2">
              <Badge variant="secondary" className="bg-slate-100 text-slate-700">
                {prettyToken(question.area)}
              </Badge>
              <Badge variant="outline" className="border-slate-200 text-slate-600">
                {prettyToken(question.eventType)}
              </Badge>
            </div>
            <p className="mb-3 font-medium text-slate-900">{question.prompt}</p>
            <div className="flex flex-wrap gap-2">
              {question.options.map((option) => (
                <Button
                  key={`${question.questionKey}-${option.value}`}
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={submittingKey === question.questionKey}
                  onClick={() => onAnswer(option.value)}
                  className={getOptionClass(question.eventType)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </motion.div>
        ) : (
          !loading && (
            <p className="text-sm text-slate-600">
              No prompt available right now.
            </p>
          )
        )}

        <div className="pt-1">
          <Link href="/preferences">
            <Button size="sm" className="rounded-lg bg-sky-600 hover:bg-sky-700">
              Open Full Preference Game
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
