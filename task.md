# TASK.md — Multi-Agent Execution Specification

## GOAL
Build and execute tasks using a dynamic multi-agent system with:
- Skill Retrieval (RAG)
- Task Graph (DAG)
- Reflection (self-correction)
- Memory (short-term & long-term)

---

## CORE WORKFLOW

Follow strictly:

1. PLAN
2. EXECUTE
3. REFLECT
4. VERIFY
5. REPORT

If assumptions break → STOP → REPLAN

---

## 1. INTENT UNDERSTANDING

Extract:
- goal
- constraints
- expected output

If unclear → ASK before proceeding

---

## 2. MEMORY RETRIEVAL

Before planning:

- Load short-term memory (current context)
- Retrieve relevant long-term memory:
  - past similar tasks
  - successful strategies

Inject into planning

---

## 3. TASK GRAPH PLANNING (DAG)

Decompose task into:

- atomic tasks (nodes)
- dependencies (edges)

Rules:
- MUST build DAG (not linear)
- Identify parallelizable tasks
- Minimize depth

Example:

TaskA → TaskB → TaskD  
     ↘ TaskC ↗  

---

## 4. SKILL RETRIEVAL (RAG)

For each task:

1. Embed task description
2. Retrieve top-k skills from Skill Registry
3. Map:
   task → skills → tools

Rules:
- NO hardcoded skills
- Prefer minimal sufficient skill set
- Avoid redundant tools

---

## 5. SUB-AGENT ASSIGNMENT

For each task node:

Create Sub-Agent with:
- task description
- selected skills
- available tools
- local context

Sub-Agent MUST:
- only execute
- not re-plan globally

---

## 6. EXECUTION (GRAPH MODE)

- Execute tasks respecting dependencies
- Run independent tasks in parallel
- Store outputs in short-term memory

---

## 7. REFLECTION (MANDATORY)

After each task:

Evaluate:
- correctness
- completeness
- consistency

Decision:

- accept → continue
- retry → adjust tools/approach
- fail → escalate / replan

Retry limit: 1

---

## 8. MEMORY WRITE

After task completion:

Store:
- task
- solution
- success/failure
- lessons learned

Update long-term memory

---

## 9. VERIFICATION

Before final result:

- check all tasks completed
- validate outputs
- ensure consistency across results

---

## 10. OUTPUT

### TASK GRAPH
- nodes
- dependencies

### SKILL MAPPING
- task → skills → tools

### EXECUTION TRACE
- per task:
  - result
  - status
  - reflection decision

### FINAL RESULT

---

## RULES

- NEVER skip planning
- NEVER skip reflection
- NEVER assume missing info
- ALWAYS prefer parallel execution
- MINIMIZE tool usage
- DO NOT hallucinate tools

---

## MEMORY STRUCTURE

### Short-Term
- current task context
- intermediate results

### Long-Term
{
  "task": "...",
  "solution": "...",
  "success": true,
  "embedding": [...]
}

---

## SKILL REGISTRY FORMAT

{
  "name": "...",
  "description": "...",
  "embedding": [...],
  "tools": [...]
}

---

## FAILURE HANDLING

If failure occurs:

1. retry once (different tool or approach)
2. if still fails:
   - mark as failed
   - escalate to replan

---

## PRINCIPLES

- Separation of concerns
- Dynamic capability composition
- Reliability over creativity
- Minimal context per agent
- Prefer many small tasks over one large task