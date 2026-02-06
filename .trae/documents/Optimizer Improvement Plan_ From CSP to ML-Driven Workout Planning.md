# Phase 0: Foundation & Metrics (Weeks 1-4)
**Goal**: Establish baseline and monitoring before ML integration

1. **Pre-Solver Validation System**
   - Implement feasibility checks before calling OR-Tools
   - Add constraint propagation and domain pruning
   - Log infeasible patterns with root cause analysis
   - Expected CSP failure reduction: 30-50%

2. **Fallback Strategy Enhancement**
   - Make fallback explicit and configurable (5-tier hierarchy)
   - Add progressive constraint relaxation thresholds
   - Implement fallback activation logging

3. **Monitoring Dashboard Setup**
   - Track CSP success/failure rates per constraint type
   - Monitor relaxation pass usage patterns
   - Alert on abnormal failure spikes (>5% baseline)
   - KPIs: CSP success rate, avg solve time, fallback usage

4. **User Notification System**
   - Add API responses with optimization status flags
   - Frontend indicators for degraded/failed optimization
   - Progressive disclosure: "Quick version" → "Full version loading" → "We couldn't generate optimal plan"

---

# Phase 1: Neural Network Prediction (Weeks 5-16)
**Goal**: Fast inference and baseline ML model

1. **Data Collection Pipeline**
   - Extract features from completed sessions: user profile, constraints, selected exercises, outcomes
   - Label: optimal/not optimal based on session completion, PRs, user modifications
   - Target: 10,000+ labeled sessions for training

2. **Model Architecture**
   - Input: 50-100 features (goals, equipment, time constraints, pattern exposure, muscle fatigue)
   - Hidden layers: 3-4 layers (256-128-64-32 neurons) with ReLU
   - Output: Exercise selection probabilities or ratings
   - Framework: PyTorch (easier integration than TensorFlow)

3. **Training & Validation**
   - Split: 70% train, 15% validation, 15% test
   - Loss: Binary cross-entropy (optimal/not) + ranking loss (pairwise preferences)
   - Early stopping based on validation loss
   - Hyperparameter tuning with Optuna

4. **Integration Pattern**
   - ML generates top 50 candidate exercises
   - OR-Tools validates constraints from candidates (reduced search space)
   - Fallback to full CSP if ML candidates are infeasible
   - Expected speedup: 5-10x (60s → 6-12s)

5. **Success Metrics**
   - Inference time: <500ms
   - CSP fallback rate: <15%
   - User satisfaction: match or exceed baseline (survey completion rates)
   - A/B test: ML vs CSP for 1,000 sessions

---

# Phase 2: Collaborative Filtering (Weeks 17-24)
**Goal**: Address cold start, improve explainability

1. **User Similarity Engine**
   - Matrix factorization: user embeddings from goals, equipment, demographics
   - Implicit feedback: session completions, PRs, skipped exercises
   - Library: LightFM (supports hybrid content-based + collaborative)

2. **Exercise Embeddings**
   - Content features: pattern, primary muscle, mechanics, equipment, discipline
   - Learned embeddings from neural net (reuse Phase 1 model)
   - Cosine similarity for "users like you liked these"

3. **Cold Start Mitigation**
   - New users: Content-based filtering (goal/equipment matching)
   - After 5 sessions: Switch to collaborative filtering
   - Hybrid: Weighted combination of content + collaborative

4. **Explainability Layer**
   - "85% of users with hypertrophy goals completed 4 sets of squats"
   - "Similar users in your age group prefer deadlift variations"
   - API returns reasoning alongside recommendations

5. **Success Metrics**
   - New user session completion rate: +20%
   - User trust score: % of recommendations accepted without modification
   - Cold start quality: First 5 sessions completion rate vs baseline

---

# Phase 3: Multi-Objective Optimization (Weeks 25-36)
**Goal**: Explore tradeoffs, user-driven selection

1. **Pareto Front Generation**
   - Replace single objective (stimulus × goal pressure) with 4 objectives:
     - Maximize hypertrophy stimulus
     - Minimize fatigue accumulation
     - Maximize movement variety
     - Minimize CNS load
   - Algorithm: NSGA-II (non-dominated sorting genetic algorithm)
   - Library: Pymoo or DEAP

2. **Pareto Front API**
   - Return 5-10 Pareto-optimal solutions per session
   - Each solution shows tradeoffs: "High volume, moderate fatigue, low variety"
   - User selects or system selects based on preferences

3. **Smart Selection Logic**
   - Neural net predicts which Pareto solution user will prefer
   - Collaborative filtering suggests solutions "similar users chose"
   - Default: Balanced middle-of-front solution

4. **Visualization**
   - Frontend radar charts showing tradeoff dimensions
   - Interactive sliders to adjust weights
   - "Show me higher variety, lower fatigue" → dynamic re-ranking

5. **Success Metrics**
   - User engagement with tradeoff UI: % who explore multiple options
   - Satisfaction: Post-session rating of selected solution
   - Pareto diversity: Number of distinct solutions users select over time

---

# Phase 4: Hybrid RL+CSP (Weeks 37-72)
**Goal**: Long-term strategy optimization

1. **Simulation Environment**
   - Simulate 1,000 virtual users with realistic behaviors
   - Reward function: session completion, PRs, retention streak
   - States: user profile, fatigue state, goal progress, equipment availability

2. **RL Agent Training**
   - Algorithm: PPO (Proximal Policy Optimization) - stable, sample-efficient
   - Action space: Select session type, pattern distribution, volume targets
   - Observation space: 100-200 features (user state, constraints, history)
   - Framework: Stable Baselines3 + Ray RLlib for distributed training

3. **Hybrid Integration**
   - RL agent sets high-level strategy (weekly pattern distribution, volume targets)
   - Multi-objective optimizer generates session-level tradeoffs
   - Neural net + collaborative filtering select specific exercises
   - CSP validates final feasibility

4. **Real-World Deployment**
   - Start with "shadow mode" - RL recommends, but CSP executes
   - Gradually increase RL influence: 10% → 25% → 50% → 100%
   - Human-in-the-loop: Coach reviews RL decisions for edge cases

5. **Continuous Learning**
   - Online fine-tuning from real user outcomes
   - Exploration: 5% of sessions try novel strategies
   - Safety limits: Never exceed physiological recovery thresholds

6. **Success Metrics**
   - Long-term outcomes: 3-month PR improvement, 6-month retention
   - Novelty: % of sessions using patterns RL discovered
   - Adaptation: How quickly RL responds to user goal changes

---

# Variable Replacement: Stimulus/Fatigue → Volume/Training Type/Variety/CNS Load

**Evidence from Data Researcher:**
- Volume is primary hypertrophy driver (28-30 sets/week per muscle group)
- Proximity-to-failure (1-2 RIR) = similar hypertrophy to training to failure
- Rep range continuum: 6-12, 12-20, 20+ all produce hypertrophy if close to failure
- CNS load distinct from peripheral fatigue (HRV best metric)

**Implementation Timeline** (parallel to ML phases):

1. **Database Schema Updates** (Weeks 1-2)
   - Add columns to movements: `volume_sets_per_week`, `cns_load_score`
   - Add training_type enum: `STRENGTH_POWER (1-5 RIR)`, `HYPERTROPHY (1-3 RIR)`, `ENDURANCE (0-1 RIR)`
   - Migrate existing data using biomechanical inference rules

2. **Algorithm Updates** (Weeks 3-4)
   - Replace `stimulus_factor` with `volume_sets_per_week` calculation
   - Replace `fatigue_factor` with `cns_load_score` × proximity_to_failure
   - Add `training_type` to objective function

3. **Validation** (Weeks 5-6)
   - Compare new vs old variable correlations with actual outcomes
   - A/B test: 500 sessions with old variables, 500 with new variables
   - Measure: session completion, PR rates, user satisfaction

4. **Rollout** (Week 7)
   - Full switch if new variables outperform baseline
   - Keep old variables as fallback for 1 month

---

# Risk Mitigation

**Technical Risks:**
- ML model degradation: Monitor drift, set up retraining pipelines
- CSP failures: Keep fallback hierarchy, never fully disable CSP
- Data quality: Implement data validation, outlier detection
- Performance: Set strict SLAs, auto-rollback if thresholds breached

**Business Risks:**
- User trust: Always provide explanations, allow manual overrides
- Cost overruns: Start with CPU inference, GPU only for training
- Timeline creep: Each phase has measurable milestones, can pause after any phase

**Rollback Plan:**
- Can revert to CSP-only at any phase boundary
- Feature flags control ML influence (0%, 25%, 50%, 75%, 100%)
- Database migrations are reversible
- Logging allows post-hoc analysis of failures

---

# Resource Requirements

**Personnel:**
- 1 ML engineer (full-time, phases 1-4)
- 1 backend engineer (50% time, integration work)
- 1 frontend engineer (25% time, UI for tradeoffs/dashboards)
- 1 data engineer (25% time, pipelines, monitoring)

**Infrastructure:**
- Development: 2x NVIDIA RTX 4090 workstations ($6,000)
- Training: AWS p3.2xlarge instances ($3/hour) for neural nets, RL
- Inference: CPU-only (existing backend servers)
- Storage: 500GB for models + training data

**Budget Estimate:**
- Phase 0: $5,000 (engineering time only)
- Phase 1: $15,000 (GPU instances + engineering)
- Phase 2: $8,000 (engineering + monitoring)
- Phase 3: $20,000 (development + A/B testing)
- Phase 4: $50,000 (RL training + simulation + gradual rollout)
- **Total**: ~$98,000 over 18 months

---

# Success Criteria by Phase

**Phase 0**: CSP failure rate reduced by 30%, monitoring dashboard operational
**Phase 1**: Session generation time <10 seconds, 85%+ ML adoption rate
**Phase 2**: New user completion rate +20%, explainability score >4/5
**Phase 3**: 50% of users explore tradeoff UI, satisfaction > baseline
**Phase 4**: 3-month PR improvement +15% vs baseline, 6-month retention +10%

**Ultimate Goal**: World's most advanced AI-powered workout optimizer that personalizes at scale while maintaining scientific rigor and explainability.