'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '../../lib/auth-context'
import {
  PreferenceQuestion,
  ProfilePreferenceProgress,
  Team,
} from '../../lib/types'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Label } from '../ui/label'

const QUESTION_LIMIT = 5

type PreferenceGameProps = {
  teams: Team[]
}

function prettyToken(value: string): string {
  return value
    .replace(/[_:]/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function getEventButtonVariant(eventType: PreferenceQuestion['eventType']): 'outline' | 'secondary' | 'destructive' {
  if (eventType === 'veto_card') {
    return 'destructive'
  }
  if (eventType === 'slider') {
    return 'secondary'
  }
  return 'outline'
}

export function PreferenceGame({ teams }: PreferenceGameProps) {
  const { api, token } = useAuth()
  const [progress, setProgress] = useState<ProfilePreferenceProgress | null>(null)
  const [questions, setQuestions] = useState<PreferenceQuestion[]>([])
  const [recommendedAreas, setRecommendedAreas] = useState<string[]>([])
  const [selectedTeamId, setSelectedTeamId] = useState('')
  const [loading, setLoading] = useState(true)
  const [submittingKey, setSubmittingKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const loadPreferenceGame = async () => {
    if (!token) {
      setLoading(false)
      setQuestions([])
      setProgress(null)
      return
    }

    try {
      setLoading(true)
      const [nextProgress, nextCatalog] = await Promise.all([
        api.getPreferenceProgress(),
        api.getPreferenceQuestions(QUESTION_LIMIT),
      ])
      setProgress(nextProgress)
      setQuestions(nextCatalog.questions)
      setRecommendedAreas(nextCatalog.recommendedAreas)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load preference game')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadPreferenceGame()
  }, [api, token])

  const submitAnswer = async (question: PreferenceQuestion, answer: string) => {
    if (!token) {
      setError('Please log in to answer preference questions.')
      return
    }

    try {
      setSubmittingKey(question.questionKey)
      setError(null)
      setNotice(null)

      await api.submitPreferenceEvent({
        eventType: question.eventType,
        questionKey: question.questionKey,
        answer,
        teamId: selectedTeamId || undefined,
      })

      const [nextProgress, nextCatalog] = await Promise.all([
        api.getPreferenceProgress(),
        api.getPreferenceQuestions(QUESTION_LIMIT),
      ])

      setProgress(nextProgress)
      setQuestions(nextCatalog.questions)
      setRecommendedAreas(nextCatalog.recommendedAreas)
      setNotice('Answer saved. New questions loaded.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save preference answer')
    } finally {
      setSubmittingKey(null)
    }
  }

  return (
    <Card className="max-w-4xl">
      <CardHeader>
        <CardTitle>Preference Game</CardTitle>
        <CardDescription>
          Add quick preference signals to improve team recommendations over time.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {!token && (
          <p className="text-sm text-slate-600">Please log in to play the preference game.</p>
        )}

        {loading && <p className="text-sm text-slate-600">Loading preference game...</p>}

        {!loading && progress && (
          <div className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Points</p>
              <p className="text-xl font-semibold text-slate-900">{progress.points}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Level</p>
              <p className="text-xl font-semibold text-slate-900">{progress.level}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Completion</p>
              <p className="text-xl font-semibold text-slate-900">{progress.completionPercent}%</p>
            </div>
          </div>
        )}

        {!loading && progress && (
          <div className="space-y-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Covered Areas</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {progress.coveredAreas.length > 0 ? (
                  progress.coveredAreas.map((area) => (
                    <Badge key={area} variant="secondary">{prettyToken(area)}</Badge>
                  ))
                ) : (
                  <p className="text-sm text-slate-600">No areas covered yet.</p>
                )}
              </div>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Suggested Next Areas</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {progress.suggestedNextAreas.length > 0 ? (
                  progress.suggestedNextAreas.map((area) => (
                    <Badge key={area} variant="outline">{prettyToken(area)}</Badge>
                  ))
                ) : (
                  <p className="text-sm text-slate-600">You have covered all default areas.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {teams.length > 0 && (
          <div className="space-y-2">
            <Label htmlFor="preference-team-context">Team Context (optional)</Label>
            <select
              id="preference-team-context"
              value={selectedTeamId}
              onChange={(event) => setSelectedTeamId(event.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">No team context</option>
              {teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {!loading && recommendedAreas.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Recommended Focus</p>
            <div className="mt-1 flex flex-wrap gap-2">
              {recommendedAreas.map((area) => (
                <Badge key={area} variant="outline">{prettyToken(area)}</Badge>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        )}

        {notice && (
          <div className="rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">{notice}</div>
        )}

        {!loading && questions.length > 0 ? (
          <div className="space-y-3">
            {questions.map((question) => (
              <div key={question.questionKey} className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{prettyToken(question.area)}</Badge>
                  <Badge variant="outline">{prettyToken(question.eventType)}</Badge>
                </div>
                <p className="font-medium text-slate-900">{question.prompt}</p>
                <div className="flex flex-wrap gap-2">
                  {question.options.map((option) => (
                    <Button
                      key={`${question.questionKey}-${option.value}`}
                      type="button"
                      variant={getEventButtonVariant(question.eventType)}
                      size="sm"
                      onClick={() => submitAnswer(question, option.value)}
                      disabled={submittingKey === question.questionKey}
                    >
                      {option.label}
                    </Button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          !loading && (
            <p className="text-sm text-slate-600">No questions available right now. Check back after more activity.</p>
          )
        )}
      </CardContent>
    </Card>
  )
}
