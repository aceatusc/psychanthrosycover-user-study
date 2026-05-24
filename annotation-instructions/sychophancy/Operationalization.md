Sycophancy refers to the tendency of a language model to prioritize user approval, agreement, or face-preservation over independent judgment, factual accuracy, or appropriate normative constraint. Across recent empirical work, sycophancy is conceptualized not merely as isolated agreement errors but as a broader behavioral pattern in which models align with user beliefs, self-image, or demands even when doing so conflicts with epistemic or ethical standards. This phenomenon has been linked to alignment procedures such as Reinforcement Learning from Human Feedback (RLHF), which may inadvertently reward agreeable or user-pleasing responses over independent reasoning. Importantly, contemporary research emphasizes that sycophancy is multi-dimensional and often emerges most clearly in multi-turn interactions rather than single responses. In line with this literature, we conceptualize sycophancy as comprising several linguistically and interactionally observable dimensions that can be experimentally manipulated while holding substantive content constant.

### **Included Dimensions**

**1\. Agreement and Propositional Alignment.**  
Several studies define sycophancy as conformity to user beliefs regardless of correctness, operationalized through flip rates, admission rates, and changes in answer accuracy. In our paradigm, this dimension captures explicit agreement markers and unqualified endorsement of the user’s framing (Sharma et al., 2024; Zhang et al., 2025; Hong et al., 2025).

**2\. Face-Preservation and Relational Validation.**  
Social or relational sycophancy involves excessive preservation of the user’s “face,” including heavy emotional validation, indirect language, and avoidance of corrective framing. The ELEPHANT framework (Cheng et al., 2025\) identifies emotional endorsement, indirect action, and accepting framing as key markers of this pattern. In therapeutic contexts, this dimension reflects the degree to which the therapist avoids mild but appropriate correction in order to protect the client’s self-image.

**3\. Praise and Flattery Intensity.**  
Sycophantic praise is distinguished from genuine encouragement by its strategic or inflated quality. Research differentiates sycophantic agreement (SYA) and sycophantic praise (SYPR) from neutral or justified agreement (Vennemeyer et al., 2025; Malmqvist, 2024). In our guideline, this dimension captures the frequency and intensity of compliments or ego-affirming statements that exceed what is therapeutically necessary.

**4\. Stance Stability Under Pressure (Flip Behavior).**  
A central insight from recent benchmarks is that sycophancy often manifests as regressive conformity across turns, particularly under repeated user pressure. Measures such as Turn-of-Flip (ToF) and Number-of-Flip (NoF) quantify how quickly and how often a model abandons its initial stance (Hong et al., 2025; Fanous et al., 2025). We therefore treat stability of professional stance across multi-turn exchanges as a core dimension of sycophancy.

**5\. Moral or Normative Endorsement (Ethical Drift).**  
In high-stakes domains such as medicine, models may acquiesce to inappropriate or harmful user requests, prioritizing empathy or agreement over guideline adherence. Clinical simulations document acquiescence rates when users request unindicated care (Peng et al., 2026). We operationalize this dimension as the degree to which the therapist maintains normative and ethical boundaries rather than endorsing problematic intentions.

**6\. Deferential Hedging.**  
While hedging is often appropriate in professional communication, excessive or strategically deployed hedging can function to avoid necessary correction and increase perceived agreeableness. Studies distinguishing progressive versus regressive sycophancy highlight how subtle linguistic shifts—particularly softening language—can signal conformity (Fanous et al., 2025; Zhang et al., 2025).

### **Rationale for Linguistic Operationalization**

Consistent with the literature, we treat these dimensions as primarily observable through surface-level linguistic cues and cross-turn interaction patterns rather than deep architectural features. By manipulating agreement markers, praise intensity, hedging, boundary clarity, and stance stability—while holding therapeutic advice, factual content, and safety guidance constant—we isolate sycophantic tendencies from substantive clinical differences. This approach mirrors contemporary multi-turn evaluations of sycophancy and allows experimental control over perceived deference versus professional independence within text-based counseling dialogues

