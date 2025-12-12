import { Pool } from 'pg';

const pool = new Pool({
  host: 'localhost',
  port: 5432,
  database: 'errorflow',
  user: 'user',
  password: 'pass',
});



export async function GET() {
  const client = await pool.connect();
  try {
    const errors = await client.query(
      'SELECT * FROM errors ORDER BY timestamp DESC'// LIMIT 20'
    );
    const groups = await client.query(
      'SELECT * FROM error_groups ORDER BY last_seen DESC NULLS LAST'// LIMIT 20'
    );
    const result = await client.query(
        `SELECT id, cluster_key, service, error_type,
                status, count, first_seen, last_seen,
                severity, ai_summary, resolution_reason, resolved_at
        FROM error_groups
        ORDER BY last_seen DESC
        LIMIT 20`
        );



    return Response.json({ errors: errors.rows, groups: groups.rows });
  } finally {
    client.release();
  }
}
