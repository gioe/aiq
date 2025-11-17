# Admin Dashboard - Question Quality Monitoring

## Overview

The IQ Tracker admin dashboard provides a comprehensive view of question performance statistics and quality metrics. This allows administrators to monitor and identify problematic questions that may need review or deactivation.

## Accessing the Dashboard

1. Ensure the admin panel is enabled in `.env`:
   ```bash
   ADMIN_ENABLED=True
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=your-secure-password
   ```

2. Start the backend server:
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --reload
   ```

3. Navigate to: http://localhost:8000/admin

4. Login with the credentials from your `.env` file

## Question Quality Dashboard

The Questions view has been enhanced with quality analytics that automatically track and display:

### Column Overview

| Column | Description |
|--------|-------------|
| **ID** | Question identifier |
| **Question Type** | Type of cognitive assessment (pattern, logic, spatial, math, verbal, memory) |
| **Difficulty Level** | LLM-assigned difficulty (easy, medium, hard) |
| **Quality** | Overall quality status badge (see below) |
| **Responses** | Number of times the question has been answered |
| **P-Value (Empirical)** | Proportion of users who answered correctly (0.0-1.0) |
| **Discrimination** | Item-total correlation (-1.0 to 1.0) - how well the question distinguishes high/low performers |
| **Arbiter Score** | LLM arbiter's quality rating |
| **Source LLM** | Which LLM generated the question |
| **Active** | Whether the question is currently active |

### Quality Status Badges

The dashboard automatically flags questions based on empirical data:

#### 📊 Pending (Gray Badge)
- **Meaning**: Insufficient response data for analysis
- **Threshold**: Less than 30 responses
- **Action**: Wait for more data before making decisions

#### ✓ Good (Green Badge)
- **Meaning**: Question performing well
- **Criteria**:
  - Sufficient responses (≥30)
  - Empirical difficulty matches LLM-assigned difficulty
  - Adequate discrimination (≥0.2)

#### ⚠ Review Needed (Red Badge)
- **Meaning**: Quality issues detected
- **Possible Issues**:
  - **Difficulty Mismatch**: Empirical difficulty doesn't match assigned level
  - **Low Discrimination**: Discrimination < 0.2 (poor ability to distinguish performers)
- **Action**: Review question text, consider revising or deactivating

### Understanding Metrics

#### P-Value (Empirical Difficulty)
- **Range**: 0.0 - 1.0 (proportion who answered correctly)
- **Interpretation**:
  - **0.7 - 1.0** (Green): Easy question
  - **0.4 - 0.7** (Yellow): Medium difficulty
  - **0.0 - 0.4** (Red): Hard question

#### Expected P-Values by Difficulty
- **Easy questions**: Should have p > 0.7
- **Medium questions**: Should have 0.4 < p < 0.7
- **Hard questions**: Should have p < 0.4

#### Discrimination
- **Range**: -1.0 to 1.0 (item-total correlation)
- **Interpretation**:
  - **≥ 0.4** (Green): Excellent discrimination
  - **0.3 - 0.4** (Blue): Good discrimination
  - **0.2 - 0.3** (Yellow): Acceptable discrimination
  - **< 0.2** (Red): Poor discrimination - review needed

#### Response Count Reliability
- **< 30**: Insufficient data (statistical unreliability)
- **30 - 100**: Marginally reliable
- **≥ 100**: Statistically reliable

### Filtering and Sorting

The dashboard supports filtering by:
- Question type
- Difficulty level
- Active status
- Source LLM
- Response count ranges
- Discrimination ranges

Click column headers to sort by that metric.

### Common Quality Issues

#### 1. Difficulty Mismatch
**Problem**: An "easy" question has a low p-value (< 0.5)

**Possible Causes**:
- Question is ambiguously worded
- Correct answer is debatable
- LLM incorrectly assessed difficulty

**Actions**:
- Review question text for clarity
- Verify correct answer
- Consider reclassifying difficulty or deactivating

#### 2. Low Discrimination
**Problem**: Discrimination < 0.2

**Possible Causes**:
- Question tests obscure knowledge rather than cognitive ability
- Question is too easy/hard for test-taker population
- Multiple interpretations possible

**Actions**:
- Review question relevance
- Consider deactivating if not improving after 100+ responses

#### 3. Negative Discrimination
**Problem**: Discrimination < 0

**Possible Causes**:
- Incorrect answer key
- Question is confusing or misleading

**Actions**:
- **Immediate review required**
- Verify correct answer
- Consider immediate deactivation

## Data Collection and Updates

### When are metrics calculated?

- **Response Count**: Updated immediately after each test submission
- **Empirical Difficulty (P-Value)**: Recalculated after each test submission
- **Discrimination**: Recalculated after each test submission (requires ≥ 2 responses)

### Minimum Data Requirements

For statistically reliable metrics:
- **Minimum**: 30 responses per question
- **Recommended**: 100+ responses for stable estimates

## Question Review Workflow

1. **Navigate to Questions** in the admin dashboard
2. **Sort by Quality** to see "Review Needed" questions first
3. **Filter by Response Count ≥ 30** to focus on statistically meaningful data
4. **Review flagged questions**:
   - Click question ID to view full details
   - Examine question text, answer options, and correct answer
   - Check p-value and discrimination values
5. **Take action**:
   - If question is salvageable: Note for future revision
   - If fundamentally flawed: Deactivate question (set `is_active = False`)

## Deactivating Questions

To deactivate a problematic question:

1. Use the admin dashboard to view question details
2. Note the question ID
3. Use database client or Django admin to update:
   ```sql
   UPDATE questions SET is_active = FALSE WHERE id = <question_id>;
   ```

**Note**: The current admin interface is read-only. To modify questions, use direct database access or extend the admin interface with edit permissions.

## Best Practices

### Regular Monitoring
- Review quality dashboard **weekly** during initial deployment
- Review **monthly** once system is stable
- Set up alerts for questions with < 0.1 discrimination

### Data-Driven Decisions
- Don't deactivate questions with < 30 responses
- Wait for 100+ responses before major decisions
- Track approval rates by source LLM to optimize generator config

### Question Pool Health
- Aim for 80%+ questions with "Good" status
- Replace deactivated questions with new generation
- Monitor distribution across types and difficulties

## Future Enhancements

Planned improvements for the question quality dashboard:

- **Automated Alerts**: Email notifications for questions flagged for review
- **Batch Actions**: Deactivate multiple questions at once
- **Trend Charts**: Visualize quality metrics over time
- **LLM Performance**: Compare arbiter scores vs empirical performance by source LLM
- **Export Reports**: Download quality reports for analysis

## Technical Details

### Implementation

The question quality dashboard is built using:
- **SQLAdmin**: Provides the admin interface framework
- **Custom Column Formatters**: Render color-coded badges and metrics
- **Database Fields**: Leverages P11-007 schema additions (empirical_difficulty, discrimination, response_count)
- **Analytics Pipeline**: P11-009 calculates metrics after each test submission

### Code Location

- Admin views: `backend/app/admin/views.py`
- Analytics logic: `backend/app/core/question_analytics.py`
- Models: `backend/app/models/models.py`

### Performance

- Dashboard queries are optimized with database indexes
- Sorting and filtering use indexed columns
- No N+1 query issues (proper relationships configured)

## Troubleshooting

### Dashboard not loading
1. Check `ADMIN_ENABLED=True` in `.env`
2. Verify admin credentials are set
3. Check server logs for errors

### Metrics showing as N/A
- Normal for new questions (< 30 responses)
- Check that question analytics (P11-009) is running after test submissions

### Quality badges not updating
- Ensure backend is restarted after code changes
- Check database for updated empirical_difficulty and discrimination values
- Verify analytics pipeline is executing (check logs during test submission)

## Support

For questions or issues with the admin dashboard:
1. Check this documentation
2. Review `backend/app/admin/views.py` code
3. Check application logs for errors
4. File an issue in the project repository
