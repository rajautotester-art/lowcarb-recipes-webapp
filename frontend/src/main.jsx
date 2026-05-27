import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`
const WELCOME_MESSAGE =
  'Ask for one type of recipe, then choose a result from the list. Try: low carb bread, papdi, cookies, pistachio, or paneer.'

function asList(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  if (!value) return []
  return [value]
}

function cleanDisplayText(value) {
  return String(value || '')
    .replace(/^\s*\d+[\.)]\s*/, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function RecipeList({ recipes, selectedRecipe, onSelect }) {
  if (!recipes.length) {
    return <p className="empty">Search results will appear here.</p>
  }

  return (
    <div className="recipe-list" role="list">
      {recipes.map((recipe) => (
        <button
          className={`recipe-option ${selectedRecipe?.recipe_id === recipe.recipe_id ? 'is-selected' : ''}`}
          key={recipe.recipe_id}
          onClick={() => onSelect(recipe)}
          type="button"
        >
          <span>{recipe.recipe_name}</span>
          <small>{recipe.category}</small>
        </button>
      ))}
    </div>
  )
}

function RecipeIndex({ recipes, selectedRecipe, onSelect }) {
  const groupedRecipes = useMemo(() => {
    return recipes.reduce((groups, recipe) => {
      const category = recipe.category || 'Recipes'
      if (!groups[category]) groups[category] = []
      groups[category].push(recipe)
      return groups
    }, {})
  }, [recipes])

  if (!recipes.length) {
    return <p className="empty">Recipe index will load here.</p>
  }

  return (
    <div className="recipe-index">
      {Object.entries(groupedRecipes).map(([category, items]) => (
        <details key={category} open>
          <summary>
            <span>{category}</span>
            <small>{items.length}</small>
          </summary>
          <div className="index-items">
            {items.map((recipe) => (
              <button
                className={`index-recipe ${
                  selectedRecipe?.recipe_id === recipe.recipe_id ? 'is-selected' : ''
                }`}
                key={recipe.recipe_id}
                onClick={() => onSelect(recipe)}
                type="button"
              >
                {recipe.recipe_name}
              </button>
            ))}
          </div>
        </details>
      ))}
    </div>
  )
}

function RecipeDetail({ recipe }) {
  if (!recipe) {
    return (
      <div className="detail-empty">
        Select a recipe from the results list to see ingredients, method, notes, and tags.
      </div>
    )
  }

  const ingredients = asList(recipe.ingredients).map(cleanDisplayText).filter(Boolean)
  const ingredientGroups = asList(recipe.ingredient_groups)
    .map((group) => ({
      section: cleanDisplayText(group.section || 'Ingredients'),
      items: asList(group.items)
        .map((item) => ({
          item: cleanDisplayText(item.item || item),
          amount: cleanDisplayText(item.amount || ''),
        }))
        .filter((item) => item.item),
    }))
    .filter((group) => group.items.length)
  const methodSteps = asList(recipe.method_steps).map(cleanDisplayText).filter(Boolean)
  const tags = asList(recipe.tags)
  const notes = cleanDisplayText(recipe.notes)

  return (
    <article className="recipe-detail">
      <div className="detail-heading">
        <div>
          <p className="eyebrow">{recipe.category}</p>
          <h2>{recipe.recipe_name}</h2>
        </div>
      </div>

      {recipe.macros && <p className="macros">{cleanDisplayText(recipe.macros)}</p>}

      <section>
        <h3>Ingredients</h3>
        {ingredientGroups.length ? (
          <div className="ingredient-groups">
            {ingredientGroups.map((group) => (
              <div className="ingredient-group" key={group.section}>
                <h4>{group.section}</h4>
                <div className="ingredient-table" role="table">
                  {group.items.map((ingredient, index) => (
                    <div className="ingredient-row" key={`${group.section}-${ingredient.item}-${index}`} role="row">
                      <span role="cell">{ingredient.item}</span>
                      <strong role="cell">{ingredient.amount}</strong>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : ingredients.length ? (
          <ul className="ingredient-list">
            {ingredients.map((ingredient, index) => (
              <li key={`${ingredient}-${index}`}>{ingredient}</li>
            ))}
          </ul>
        ) : (
          <p className="empty">No ingredients parsed yet.</p>
        )}
      </section>

      <section>
        <h3>Method</h3>
        {methodSteps.length ? (
          <ol className="method-list">
            {methodSteps.map((step, index) => (
              <li key={`${step}-${index}`}>{step}</li>
            ))}
          </ol>
        ) : (
          notes ? <p className="notes-text">{notes}</p> : <p className="empty">No method parsed yet.</p>
        )}
      </section>

      {notes && methodSteps.length === 0 && (
        <section>
          <h3>Notes</h3>
          <p className="notes-text">{notes}</p>
        </section>
      )}

      <div className="tag-list">
        {tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
    </article>
  )
}

function App() {
  const [messages, setMessages] = useState([{ role: 'assistant', content: WELCOME_MESSAGE }])
  const [input, setInput] = useState('')
  const [allRecipes, setAllRecipes] = useState([])
  const [recipes, setRecipes] = useState([])
  const [selectedRecipe, setSelectedRecipe] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeMobileView, setActiveMobileView] = useState('index')
  const allRecipesRef = useRef([])
  const recipesRef = useRef([])
  const selectedRecipeRef = useRef(null)
  const activeMobileViewRef = useRef('index')

  useEffect(() => {
    allRecipesRef.current = allRecipes
  }, [allRecipes])

  useEffect(() => {
    recipesRef.current = recipes
  }, [recipes])

  useEffect(() => {
    selectedRecipeRef.current = selectedRecipe
  }, [selectedRecipe])

  useEffect(() => {
    activeMobileViewRef.current = activeMobileView
  }, [activeMobileView])

  function recipesByIds(recipeIds = []) {
    const recipeMap = new Map(allRecipesRef.current.map((recipe) => [recipe.recipe_id, recipe]))
    return recipeIds.map((recipeId) => recipeMap.get(recipeId)).filter(Boolean)
  }

  function recipeById(recipeId, fallbackRecipes = []) {
    if (!recipeId) return null
    return (
      fallbackRecipes.find((recipe) => recipe.recipe_id === recipeId) ||
      allRecipesRef.current.find((recipe) => recipe.recipe_id === recipeId) ||
      null
    )
  }

  function currentHistoryState(overrides = {}) {
    return {
      app: 'lowcarb-recipe-chatbot',
      view: activeMobileViewRef.current,
      selectedRecipeId: selectedRecipeRef.current?.recipe_id || null,
      resultRecipeIds: recipesRef.current.map((recipe) => recipe.recipe_id),
      ...overrides,
    }
  }

  function hashForState(state) {
    const params = new URLSearchParams()
    params.set('view', state.view || 'index')
    if (state.selectedRecipeId) params.set('recipe', state.selectedRecipeId)
    if (state.resultRecipeIds?.length) params.set('results', state.resultRecipeIds.join(','))
    return `#${params.toString()}`
  }

  function stateFromHash() {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''))
    return {
      app: 'lowcarb-recipe-chatbot',
      view: params.get('view') || 'index',
      selectedRecipeId: params.get('recipe') || null,
      resultRecipeIds: (params.get('results') || '').split(',').filter(Boolean),
    }
  }

  function pushAppHistory(overrides = {}) {
    const state = currentHistoryState(overrides)
    window.history.pushState(state, '', hashForState(state))
  }

  function applyHistoryState(state) {
    if (!state || state.app !== 'lowcarb-recipe-chatbot') return
    const nextRecipes = recipesByIds(state.resultRecipeIds || [])
    const nextSelectedRecipe = recipeById(state.selectedRecipeId, nextRecipes)

    setRecipes(nextRecipes)
    setSelectedRecipe(nextSelectedRecipe)
    setActiveMobileView(state.view || 'index')
    setError('')
  }

  useEffect(() => {
    const initialState = window.location.hash ? stateFromHash() : currentHistoryState({ view: 'index' })
    window.history.replaceState(initialState, '', hashForState(initialState))

    function handlePopState(event) {
      applyHistoryState(event.state || stateFromHash())
    }

    function handleHashChange() {
      applyHistoryState(stateFromHash())
    }

    window.addEventListener('popstate', handlePopState)
    window.addEventListener('hashchange', handleHashChange)
    return () => {
      window.removeEventListener('popstate', handlePopState)
      window.removeEventListener('hashchange', handleHashChange)
    }
  }, [])

  useEffect(() => {
    async function loadRecipeIndex() {
      try {
        const response = await fetch(`${API_BASE_URL}/recipes`)
        if (!response.ok) throw new Error(`Backend returned ${response.status}`)
        const data = await response.json()
        setAllRecipes(data)
        allRecipesRef.current = data
        if (window.location.hash) {
          applyHistoryState(stateFromHash())
        }
      } catch (err) {
        setError(`Could not load recipe index. ${err.message}`)
      }
    }

    loadRecipeIndex()
  }, [])

  function clearConversation() {
    setMessages([{ role: 'assistant', content: WELCOME_MESSAGE }])
    setInput('')
    setRecipes([])
    setSelectedRecipe(null)
    setError('')
    setActiveMobileView('index')
    pushAppHistory({ view: 'index', selectedRecipeId: null, resultRecipeIds: [] })
  }

  function goHome() {
    setRecipes([])
    setSelectedRecipe(null)
    setError('')
    setActiveMobileView('index')
    pushAppHistory({ view: 'index', selectedRecipeId: null, resultRecipeIds: [] })
  }

  function goToMatches() {
    setSelectedRecipe(null)
    setActiveMobileView('matches')
    pushAppHistory({
      view: 'matches',
      selectedRecipeId: null,
      resultRecipeIds: recipesRef.current.map((recipe) => recipe.recipe_id),
    })
  }

  function changeMobileView(view) {
    setActiveMobileView(view)
    pushAppHistory({ view })
  }

  function selectRecipe(recipe) {
    setSelectedRecipe(recipe)
    setRecipes([recipe])
    setActiveMobileView('detail')
    pushAppHistory({
      view: 'detail',
      selectedRecipeId: recipe.recipe_id,
      resultRecipeIds: [recipe.recipe_id],
    })
  }

  function selectSearchResult(recipe) {
    setSelectedRecipe(recipe)
    setActiveMobileView('detail')
    pushAppHistory({
      view: 'detail',
      selectedRecipeId: recipe.recipe_id,
      resultRecipeIds: recipesRef.current.map((result) => result.recipe_id),
    })
  }

  async function sendMessage(event) {
    event.preventDefault()
    const text = input.trim()
    if (!text || isLoading) return

    setMessages((current) => [...current, { role: 'user', content: text }])
    setInput('')
    setRecipes([])
    setSelectedRecipe(null)
    setError('')
    setIsLoading(true)

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`)
      }

      const data = await response.json()
      const nextRecipes = data.recipes || []
      const nextSelectedRecipe = nextRecipes.length === 1 ? nextRecipes[0] : null
      const nextView = nextRecipes.length === 1 ? 'detail' : 'matches'
      setMessages((current) => [...current, { role: 'assistant', content: data.reply }])
      setRecipes(nextRecipes)
      setSelectedRecipe(nextSelectedRecipe)
      setActiveMobileView(nextView)
      pushAppHistory({
        view: nextView,
        selectedRecipeId: nextSelectedRecipe?.recipe_id || null,
        resultRecipeIds: nextRecipes.map((recipe) => recipe.recipe_id),
      })
    } catch (err) {
      setError(`Could not reach the recipe API. ${err.message}`)
      setActiveMobileView('chat')
      pushAppHistory({ view: 'chat', selectedRecipeId: null, resultRecipeIds: [] })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="app-shell" data-mobile-view={activeMobileView}>
      <nav className="mobile-tabs" aria-label="Mobile sections">
        {[
          ['index', 'Index'],
          ['chat', 'Chat'],
          ['matches', `Matches ${recipes.length}`],
          ['detail', 'Recipe'],
        ].map(([view, label]) => (
          <button
            className={activeMobileView === view ? 'is-active' : ''}
            key={view}
            onClick={() => changeMobileView(view)}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      <section className="chat-panel">
        <header className="app-header">
          <div>
            <p className="eyebrow">Eggless Low-Carb Indian Recipes</p>
            <h1>Recipe Chatbot</h1>
          </div>
          <button className="ghost-button" onClick={clearConversation} type="button">Clear</button>
        </header>

        <section className="index-panel" aria-label="Recipe index">
          <div className="panel-title">
            <h2>Recipe Index</h2>
            <span>{allRecipes.length}</span>
          </div>
          <RecipeIndex recipes={allRecipes} selectedRecipe={selectedRecipe} onSelect={selectRecipe} />
        </section>

        <div className="messages">
          {messages.map((message, index) => (
            <div className={`message message--${message.role}`} key={`${message.role}-${index}`}>
              {message.content}
            </div>
          ))}
          {isLoading && <div className="message message--assistant">Searching recipes...</div>}
        </div>

        {error && <div className="error">{error}</div>}

        <form className="chat-form" onSubmit={sendMessage}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Try: low carb bread"
          />
          <button type="submit" disabled={isLoading}>
            Search
          </button>
        </form>
      </section>

      <aside className="results-panel">
        <div className="results-header">
          <h2>Matches</h2>
          <span>{recipes.length}</span>
        </div>
        <RecipeList recipes={recipes} selectedRecipe={selectedRecipe} onSelect={selectSearchResult} />
      </aside>

      <section className="detail-panel">
        <RecipeDetail recipe={selectedRecipe} />
      </section>

      <nav className="mobile-bottom-actions" aria-label="Mobile navigation shortcuts">
        {activeMobileView === 'detail' && recipes.length > 1 && (
          <button className="mobile-secondary-action" onClick={goToMatches} type="button">
            Matches
          </button>
        )}
        <button className="mobile-home-action" onClick={goHome} type="button">
          Home
        </button>
      </nav>
    </main>
  )
}

createRoot(document.getElementById('root')).render(<App />)
