---
name: pixellab-create-character
description: Create pixel art characters using PixelLab MCP with guided prompts for style consistency. Asks for description, size, art style, and validates against the project's existing art direction. Use this when the user wants to create a new character sprite for the game.
domain: art
type: generator
version: 1.0.0
allowed-tools:
  - mcp__pixellab__create_character
  - mcp__pixellab__list_characters
  - mcp__pixellab__get_character
  - Read
  - Glob
  - AskUserQuestion
---

# PixelLab Character Creator Skill

This skill creates pixel art characters using the PixelLab MCP service through an **interactive questioning process**, ensuring art style consistency with the Blood & Gold project.

---

## When to Use This Skill

Invoke this skill when the user:
- Asks to "create a character" or "make a sprite"
- Says "I need a new character for the game"
- Wants to add enemies, NPCs, companions, or soldiers
- Says "generate a character with PixelLab"
- Needs pixel art sprites for any game entity

---

## Project Art Direction Context

### Blood & Gold Art Style Guidelines

**Setting:** Dark Fantasy (Low Magic) - The Shattered Kingdoms
**Perspective:** Top-down (for combat grid) with "low top-down" or "high top-down" camera angles
**Tone:** Gritty, medieval, war-torn

**Character Categories & Recommended Sizes:**
| Category | Canvas Size | Character Height | Use Case |
|----------|-------------|------------------|----------|
| Player/Companions | 48-64px | ~29-38px | Main party members |
| Soldiers (NPC) | 32-48px | ~19-29px | Recruitable infantry, archers |
| Enemies (Standard) | 32-48px | ~19-29px | Bandits, soldiers |
| Enemies (Elite) | 48-64px | ~29-38px | Knights, mages, leaders |
| Bosses | 64-96px | ~38-58px | Kingdom champions, monsters |
| NPCs (Non-combat) | 32-48px | ~19-29px | Quest givers, merchants |

**Default Style Settings (Blood & Gold Consistency):**
```
outline: "single color black outline"
shading: "basic shading" or "medium shading"
detail: "medium detail"
view: "low top-down" (combat) or "high top-down" (world map)
n_directions: 8 (for combat units) or 4 (for NPCs)
```

**Color Palette Guidance:**
- **Ironmark (North):** Steel grays, iron blues, military reds
- **Silvermere (South):** Rich purples, gold accents, merchant colors
- **Thornwood (West):** Forest greens, earthy browns, natural tones
- **Sunspire (East):** Desert golds, arcane purples, sandy tones
- **Ashenvale (Center):** Ashen grays, sickly greens, corruption purples
- **Bandits/Outlaws:** Worn browns, dirty leather, ragged cloth
- **Undead:** Pale bone whites, ethereal blues, decay greens

**Proportion Presets:**
- `default` - Standard humanoid proportions
- `chibi` - Cute, large head (NOT recommended for Blood & Gold)
- `heroic` - Slightly exaggerated heroic proportions (good for player characters)
- `realistic_male` / `realistic_female` - More realistic body ratios

---

## Interactive Workflow

### Phase 1: Character Concept

**Start by asking these questions:**

```
I'll help you create a new character using PixelLab! Let's define the concept:

**1. Character Role**
What type of character is this?
- [ ] Player Character / Companion
- [ ] Enemy (Standard)
- [ ] Enemy (Elite/Boss)
- [ ] NPC Soldier (recruitable)
- [ ] NPC (non-combat)
- [ ] Other: _______

**2. Character Description**
Describe the character's appearance in detail:
- What are they wearing? (armor type, clothing style)
- What weapons/equipment do they carry?
- Any distinctive features? (scars, hair color, pose)
- What kingdom/faction do they belong to?

Example: "Ironmark heavy infantry soldier in plate armor with tower shield and longsword, stern expression, military bearing"

**3. Kingdom/Faction Affiliation**
Which faction does this character belong to?
- [ ] Ironmark (military, honor-bound)
- [ ] Silvermere (merchant, wealthy)
- [ ] Thornwood (druidic, nature)
- [ ] Sunspire (magical, academic)
- [ ] Ashenvale (outcasts, corrupted)
- [ ] Bandits/Outlaws
- [ ] Neutral/Independent
```

**Wait for user response before proceeding.**

---

### Phase 2: Technical Specifications

**After receiving Phase 1 answers, ask:**

```
Great! Now let's define the technical specifications:

**4. Canvas Size**
Based on the character role, I recommend:
[Provide recommendation based on role from Phase 1]

What size would you like?
- [ ] 32px (small units, NPCs)
- [ ] 48px (standard units, companions)
- [ ] 64px (player character, elites)
- [ ] 96px (bosses, large creatures)
- [ ] 128px (very large, special cases)
- [ ] Custom: _______

**5. Directional Views**
How many directions should the sprite have?
- [ ] 4 directions (south, west, east, north) - simpler, NPCs
- [ ] 8 directions (includes diagonals) - combat units, player

**6. Camera Angle**
Which perspective?
- [ ] low top-down (Recommended - closer to ground, better for combat)
- [ ] high top-down (more bird's eye view)
- [ ] side (platformer style - NOT typical for Blood & Gold)
```

**Wait for user response before proceeding.**

---

### Phase 3: Art Style Settings

**After receiving Phase 2 answers, ask:**

```
Now let's set the art style to match Blood & Gold:

**7. Outline Style**
- [ ] single color black outline (Recommended - clean, readable)
- [ ] single color outline (colored outline)
- [ ] selective outline (outline only where needed)
- [ ] lineless (no outline - not recommended for Blood & Gold)

**8. Shading Complexity**
- [ ] flat shading (minimal shadows)
- [ ] basic shading (Recommended - good balance)
- [ ] medium shading (more depth)
- [ ] detailed shading (complex lighting)

**9. Detail Level**
- [ ] low detail (simpler, faster reads)
- [ ] medium detail (Recommended - balanced)
- [ ] high detail (intricate, for larger sprites)

**10. Body Proportions**
- [ ] default (standard proportions)
- [ ] heroic (slightly larger, heroic feel - good for player/companions)
- [ ] realistic_male / realistic_female (more realistic)
- [ ] Custom proportions (specify values)
```

**Wait for user response before proceeding.**

---

### Phase 4: Review & Generate

**After gathering all answers, present a summary:**

```
Here's the character I'll create:

**Character Summary:**
- Description: [Full description from Phase 1]
- Role: [Character role]
- Faction: [Kingdom/faction]

**Technical Settings:**
- Canvas Size: [X]px (character ~60% of canvas)
- Directions: [4/8]
- View: [low/high top-down]

**Art Style:**
- Outline: [style]
- Shading: [complexity]
- Detail: [level]
- Proportions: [preset]

**Estimated Generation Time:** 2-3 minutes (4 directions) or 3-5 minutes (8 directions)

Ready to generate? [Yes / Modify settings]
```

---

### Phase 5: Execute Generation

**Once confirmed, call the PixelLab API:**

```gdscript
# Use the mcp__pixellab__create_character tool with these parameters:
{
  "description": "[Full character description]",
  "name": "[Character name for reference]",
  "size": [canvas size],
  "n_directions": [4 or 8],
  "view": "[low top-down / high top-down / side]",
  "outline": "[outline style]",
  "shading": "[shading level]",
  "detail": "[detail level]",
  "proportions": "{\"type\": \"preset\", \"name\": \"[preset name]\"}"
}
```

**After submission:**
```
Character creation job queued!

**Job Details:**
- Character ID: [ID from response]
- Status: Processing
- Estimated Time: 2-5 minutes

**Next Steps:**
1. The character will generate in the background
2. Use `/pixellab-check-status` or ask me to check on it
3. Once complete, you can download the sprite or add animations

**Tip:** While waiting, you can queue more characters or work on other tasks!
```

---

## Description Writing Guidelines

### Effective PixelLab Prompts

**DO Include:**
- Specific clothing/armor type (plate armor, leather tunic, robes)
- Weapon being held or visible
- Faction colors or identifying marks
- Pose or stance (combat ready, relaxed, aggressive)
- Key visual features (beard, helmet, cape)

**DON'T Include:**
- Backstory or personality (focus on VISUAL elements)
- Environmental details (background, location)
- Actions (walking, attacking - that's for animations)
- Overly long descriptions (keep under 200 words)

### Example Descriptions by Faction

**Ironmark Infantry:**
```
Ironmark heavy infantry soldier in steel plate armor with chainmail
underneath, carrying a tower shield emblazoned with iron fist emblem,
longsword at hip, military red cape, stern bearded face, combat stance
```

**Thornwood Ranger:**
```
Thornwood ranger in forest green leather armor with leaf patterns,
hooded cloak, longbow across back, quiver of arrows, wiry athletic
build, face partially hidden by hood, alert scouting pose
```

**Bandit Leader:**
```
Scarred bandit leader in mismatched leather and chain armor,
fur-lined cloak, dual short swords, eye patch over left eye,
menacing grin, confident aggressive stance
```

**Silvermere Merchant Guard:**
```
Silvermere merchant guild guard in purple and gold livery over
chainmail, ornate halberd, plumed helmet, clean well-maintained
equipment, professional at-attention pose
```

**Sunspire Battlemage:**
```
Sunspire battlemage in flowing arcane robes of deep blue with
golden runes, crystal-topped staff, magical energy around hands,
bald head with arcane tattoos, casting stance
```

---

## Validation Checklist

Before generating, verify:

- [ ] Description focuses on visual elements only
- [ ] Size is appropriate for character role
- [ ] Style settings match Blood & Gold aesthetic
- [ ] Faction colors are consistent with lore
- [ ] Proportions suit the character type
- [ ] Direction count matches intended use (4 for NPCs, 8 for combat)

---

## Post-Generation Workflow

**After character generates:**

1. **Check Status:**
   ```
   Use mcp__pixellab__get_character with the character_id to check completion
   ```

2. **Review Output:**
   - Verify all directions rendered correctly
   - Check style consistency
   - Confirm character reads well at game resolution

3. **Add Animations (if needed):**
   ```
   Use the pixellab-animate-character skill to add:
   - Idle animation (breathing-idle)
   - Walk cycle (walking-8-frames)
   - Attack animations (depends on weapon)
   - Death animation (falling-back-death)
   ```

4. **Download Assets:**
   ```
   The character response includes download URLs for:
   - Individual direction PNGs
   - Sprite sheet
   - ZIP with all assets
   ```

5. **Import to Godot:**
   - Save to `assets/sprites/characters/[faction]/[character_name]/`
   - Create AnimatedSprite2D or AnimationPlayer
   - Set up animation states

---

## Quick Generation (Skip Interactive)

If user provides all details upfront, skip the questions and generate directly:

**Example:**
```
User: "Create a 48px Ironmark knight with 8 directions"

Skip to Phase 5 with:
- description: "Ironmark knight in full plate armor, tower shield, longsword, red cape with iron fist emblem, heroic stance"
- name: "Ironmark Knight"
- size: 48
- n_directions: 8
- view: "low top-down"
- outline: "single color black outline"
- shading: "basic shading"
- detail: "medium detail"
- proportions: {"type": "preset", "name": "heroic"}
```

---

## Error Handling

**If generation fails:**
1. Check PixelLab service status
2. Verify description isn't too long (>500 chars can cause issues)
3. Try simplifying the description
4. Check subscription/credits status

**If style doesn't match:**
1. Regenerate with adjusted settings
2. Try different shading level
3. Modify description for clarity
4. Use reference to existing successful characters

---

## Example Invocations

User: "I need a new enemy type for the bandit camp"
User: "Create a character sprite for the Thornwood druid"
User: "Make a boss sprite for the Ironmark Knight Commander"
User: "Generate pixel art for the player character fighter class"
User: "I need soldier sprites for the recruitable infantry"

---

## Reference: Existing Project Characters

Check existing characters for style consistency:
```
Use mcp__pixellab__list_characters to see:
- Combat Mech (64x64, 8 directions) - reference for larger units
- Knight (48x48, 8 directions) - reference for standard combat units
- Cave Explorer (32x32, 4 directions) - reference for smaller NPCs
```

Match new characters to these established styles for visual consistency.
