// MP-Declare models that agents are checked against.

import { useCallback, useEffect, useState } from 'react'
import { ApiError, apiFetch, errorMessage } from '../api'
import { useSession } from './Auth'

/** Mirrors ModelInfo in src/governancekit/server/main.py. */
type ModelInfo = {
  model_id: string
  constraint_count: number
}

async function listModels(token: string): Promise<ModelInfo[]> {
  const res = await apiFetch('/models', token)
  const body: { models: ModelInfo[] } = await res.json()
  return body.models
}

/** A model's MP-Declare text, as it was added. */
async function getModelText(token: string, modelId: string): Promise<string> {
  const res = await apiFetch(`/models/${encodeURIComponent(modelId)}`, token)
  const body: { decl: string } = await res.json()
  return body.decl
}

export function ModelList() {
  const { token, logOut } = useSession()
  const [models, setModels] = useState<ModelInfo[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // ID of the model whose text is shown
  const [selected, setSelected] = useState<string | null>(null)

  // State is only set in the promise callbacks, after the request finishes
  const load = useCallback(
    () =>
      listModels(token).then(
        (result) => {
          setModels(result)
          setError(null)
        },
        (e) => {
          // Expired or invalid token: go back to the login form
          if (e instanceof ApiError && e.status === 401) logOut()
          else setError(errorMessage(e))
        },
      ),
    [token, logOut],
  )

  // Load when the component appears
  useEffect(() => {
    load()
  }, [load])

  function toggle(modelId: string) {
    setSelected((current) => (current === modelId ? null : modelId))
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2>Declare Models</h2>
      </div>
      {error && <p className="error">{error}</p>}
      {models === null && !error && <p>Loading…</p>}
      {models?.length === 0 && <p>No models added yet.</p>}
      {models && models.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Constraints</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <ModelRow
                key={model.model_id}
                model={model}
                open={selected === model.model_id}
                onToggle={() => toggle(model.model_id)}
              />
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function ModelRow({
  model,
  open,
  onToggle,
}: {
  model: ModelInfo
  open: boolean
  onToggle: () => void
}) {
  const { token, logOut } = useSession()
  // Fetched the first time the row is opened; a model's text never changes
  const [text, setText] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || text !== null) return
    getModelText(token, model.model_id).then(
      (result) => {
        setText(result)
        setError(null)
      },
      (e) => {
        if (e instanceof ApiError && e.status === 401) logOut()
        else setError(errorMessage(e))
      },
    )
  }, [open, text, token, model.model_id, logOut])

  return (
    <>
      <tr
        className="clickable"
        tabIndex={0}
        aria-expanded={open}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onToggle()
          }
        }}
      >
        <td>
          <code>{model.model_id}</code>
        </td>
        <td>{model.constraint_count}</td>
      </tr>
      {open && (
        <tr className="details">
          <td colSpan={2}>
            {error && <p className="error">{error}</p>}
            {text === null && !error && <p>Loading…</p>}
            {text !== null && <pre className="decl">{text.trim()}</pre>}
          </td>
        </tr>
      )}
    </>
  )
}
