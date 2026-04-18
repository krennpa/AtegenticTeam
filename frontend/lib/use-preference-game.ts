'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAuth } from './auth-context'
import { PreferenceQuestion, ProfilePreferenceProgress } from './types'

type UsePreferenceGameOptions = {
  questionLimit?: number
  autoLoad?: boolean
}

type SubmitPreferenceAnswerOptions = {
  teamId?: string
  successMessage?: string
}

type UsePreferenceGameResult = {
  progress: ProfilePreferenceProgress | null
  questions: PreferenceQuestion[]
  recommendedAreas: string[]
  loading: boolean
  submittingKey: string | null
  error: string | null
  notice: string | null
  refresh: () => Promise<void>
  submitAnswer: (
    question: PreferenceQuestion,
    answer: string,
    options?: SubmitPreferenceAnswerOptions
  ) => Promise<boolean>
  dismissNotice: () => void
}

const DEFAULT_LIMIT = 5

export function usePreferenceGame(options: UsePreferenceGameOptions = {}): UsePreferenceGameResult {
  const { questionLimit = DEFAULT_LIMIT, autoLoad = true } = options
  const { api, token } = useAuth()

  const [progress, setProgress] = useState<ProfilePreferenceProgress | null>(null)
  const [questions, setQuestions] = useState<PreferenceQuestion[]>([])
  const [recommendedAreas, setRecommendedAreas] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [submittingKey, setSubmittingKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!token) {
      setProgress(null)
      setQuestions([])
      setRecommendedAreas([])
      setError(null)
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const [nextProgress, nextCatalog] = await Promise.all([
        api.getPreferenceProgress(),
        api.getPreferenceQuestions(questionLimit),
      ])
      setProgress(nextProgress)
      setQuestions(nextCatalog.questions)
      setRecommendedAreas(nextCatalog.recommendedAreas)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load preference game')
    } finally {
      setLoading(false)
    }
  }, [api, questionLimit, token])

  useEffect(() => {
    if (autoLoad) {
      void refresh()
    }
  }, [autoLoad, refresh])

  const submitAnswer = useCallback(
    async (
      question: PreferenceQuestion,
      answer: string,
      submitOptions?: SubmitPreferenceAnswerOptions
    ) => {
      if (!token) {
        setError('Please log in to answer preference questions.')
        return false
      }

      try {
        setSubmittingKey(question.questionKey)
        setError(null)
        setNotice(null)

        await api.submitPreferenceEvent({
          eventType: question.eventType,
          questionKey: question.questionKey,
          answer,
          teamId: submitOptions?.teamId,
        })

        await refresh()
        setNotice(submitOptions?.successMessage ?? 'Answer saved. New questions loaded.')
        return true
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to save preference answer')
        return false
      } finally {
        setSubmittingKey(null)
      }
    },
    [api, refresh, token]
  )

  const dismissNotice = useCallback(() => setNotice(null), [])

  return {
    progress,
    questions,
    recommendedAreas,
    loading,
    submittingKey,
    error,
    notice,
    refresh,
    submitAnswer,
    dismissNotice,
  }
}
