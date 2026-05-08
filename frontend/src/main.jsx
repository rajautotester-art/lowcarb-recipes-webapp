import React, { useEffect, useMemo, useState } from 'react'
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

  const ingredients = asList(recipe.ingredients)
  const methodSteps = asList(recipe.method_steps)
  const tags = asList(recipe.tags)

  return (
    <article className="recipe-detail">
      <div className="detail-heading">
        <div>
          <p className="eyebrow">{recipe.category}</p>
          <h2>{recipe.recipe_name}</h2>
        </div>
      </div>

      {recipe.macros && <p className="macros">{recipe.macros}</p>}

      <section>
        <h3>Ingredients</h3>
        {ingredients.length ? (
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
          <p>{recipe.notes}</p>
        )}
      </section>

      {recipe.notes && methodSteps.length === 0 && (
        <section>
          <h3>Notes</h3>
          <p>{recipe.notes}</p>
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

  useEffect(() => {
    async function loadRecipeIndex() {
      try {
        const response = await fetch(`${API_BASE_URL}/recipes`)
        if (!response.ok) throw new Error(`Backend returned ${response.status}`)
        const data = await response.json()
        setAllRecipes(data)
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
  }

  function selectRecipe(recipe) {
    setSelectedRecipe(recipe)
    setRecipes([recipe])
    setActiveMobileView('detail')
  }

  function selectSearchResult(recipe) {
    setSelectedRecipe(recipe)
    setActiveMobileView('detail')
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
      setMessages((current) => [...current, { role: 'assistant', content: data.reply }])
      setRecipes(nextRecipes)
      setSelectedRecipe(nextRecipes.length === 1 ? nextRecipes[0] : null)
      setActiveMobileView(nextRecipes.length === 1 ? 'detail' : 'matches')
    } catch (err) {
      setError(`Could not reach the recipe API. ${err.message}`)
      setActiveMobileView('chat')
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
            onClick={() => setActiveMobileView(view)}
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
    </main>
  )
}

createRoot(document.getElementById('root')).render(<App />)
