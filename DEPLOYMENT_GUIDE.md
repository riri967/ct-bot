# 🚀 Deployment Guide: Human Study with Supabase

## Quick Setup for Online Deployment

### 1. **Supabase Setup (2 minutes)**

1. Go to [supabase.com](https://supabase.com) and create account
2. Create new project
3. Go to **Settings > API** and copy:
   - Project URL 
   - `anon` `public` key

### 2. **Create Supabase Tables**

Run this SQL in Supabase SQL Editor:

```sql
-- Participants table
CREATE TABLE participants (
    id TEXT PRIMARY KEY,
    start_time TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    status TEXT DEFAULT 'active'
);

-- Conversations table  
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    participant_id TEXT REFERENCES participants(id),
    user_message TEXT,
    ai_response TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Questionnaire responses
CREATE TABLE questionnaire_responses (
    id SERIAL PRIMARY KEY,
    participant_id TEXT REFERENCES participants(id),
    age INTEGER,
    education TEXT,
    ct_experience TEXT,
    post_q1_easy_to_use INTEGER,
    post_q2_felt_confident INTEGER,
    post_q3_use_again INTEGER,
    post_q4_engaging INTEGER,
    post_q5_natural_flow INTEGER,
    post_q6_disengagement TEXT,
    post_q7_encouraged_reflection INTEGER,
    post_q8_multiple_perspectives INTEGER,
    post_q9_critical_thinking_ways TEXT,
    post_q10_learned_something TEXT,
    post_q11_design_support TEXT,
    post_q12_confusion TEXT,
    post_q13_application TEXT,
    post_q14_improvements TEXT,
    post_q15_valuable INTEGER,
    post_q16_recommend INTEGER,
    post_q17_other_comments TEXT,
    facione_critical_thinking_score REAL,
    completion_time TIMESTAMPTZ DEFAULT NOW()
);

-- Study scenarios
CREATE TABLE study_scenarios (
    id SERIAL PRIMARY KEY,
    participant_id TEXT REFERENCES participants(id),
    scenario_text TEXT,
    initial_question TEXT,
    generation_timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE questionnaire_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_scenarios ENABLE ROW LEVEL SECURITY;

-- Create policies to allow all operations (for app use)
CREATE POLICY "Allow all operations on participants" ON participants FOR ALL USING (true);
CREATE POLICY "Allow all operations on conversations" ON conversations FOR ALL USING (true);
CREATE POLICY "Allow all operations on questionnaire_responses" ON questionnaire_responses FOR ALL USING (true);
CREATE POLICY "Allow all operations on study_scenarios" ON study_scenarios FOR ALL USING (true);
```

### 3. **Deploy to Streamlit Cloud**

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set **App path**: `human_study/streamlit_app.py`

### 4. **Configure Secrets**

In Streamlit Cloud, go to **App settings > Secrets** and add:

```toml
# API Keys
GEMINI_API_KEY_1 = "your_gemini_api_key"
GEMINI_API_KEY_2 = "your_gemini_api_key" 
GEMINI_API_KEY_3 = "your_gemini_api_key"

# Supabase Configuration
supabase_url = "https://your-project.supabase.co"
supabase_key = "your_anon_public_key_here"
```

### 5. **Access Your Deployed Study**

- **Public Study**: `https://your-app.streamlit.app/`
- **Admin Panel**: `https://your-app.streamlit.app/?admin=true`

## ✅ Verification Checklist

- [ ] Supabase project created
- [ ] All 4 tables created in Supabase 
- [ ] RLS policies enabled
- [ ] Streamlit app deployed
- [ ] Secrets configured
- [ ] Test participant flow works
- [ ] Admin panel accessible
- [ ] Data appears in Supabase tables

## 📊 Monitoring Your Study

### Real-time Data Access:
1. **Supabase Dashboard**: View all data in real-time tables
2. **Admin Panel**: `your-app.streamlit.app/?admin=true`
3. **Export Data**: Download CSV files from admin panel

### Key Metrics to Watch:
- Total participants visiting
- Active conversation rate
- Average exchanges per participant  
- Completion rate (questionnaires filled)

## 🔧 Troubleshooting

**Supabase Connection Failed**: 
- Check URL and key in secrets
- Verify RLS policies are set

**No Data Showing**:
- Check Supabase tables have data
- Verify admin panel shows "Supabase" as database type

**Deployment Issues**:
- Check requirements.txt includes `supabase>=2.0.0`
- Verify secrets are properly formatted (no extra spaces)

## 📈 Data Flow

```
Participant → Streamlit App → Supabase Database → Admin Panel → CSV Export
```

Your study data is now automatically logged to Supabase in real-time and accessible via the admin panel!