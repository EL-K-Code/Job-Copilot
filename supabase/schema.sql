-- JobCopilot durable beta persistence for Supabase.
-- Run this once in Supabase -> SQL Editor before enabling PERSISTENCE_BACKEND=supabase.

create table if not exists public.jobcopilot_state (
    user_id text not null,
    namespace text not null,
    payload jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    primary key (user_id, namespace)
);

create table if not exists public.jobcopilot_usage (
    user_id text not null,
    day date not null,
    used integer not null default 0 check (used >= 0),
    operations jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    primary key (user_id, day)
);

-- The browser never talks directly to these tables. JobCopilot accesses them only
-- from the Streamlit server through the service-role secret.
alter table public.jobcopilot_state enable row level security;
alter table public.jobcopilot_usage enable row level security;

revoke all on table public.jobcopilot_state from anon, authenticated;
revoke all on table public.jobcopilot_usage from anon, authenticated;

create or replace function public.jobcopilot_consume_quota(
    p_user_id text,
    p_day date,
    p_operation text,
    p_limit integer
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    current_used integer;
    current_operations jsonb;
    next_operations jsonb;
begin
    if p_limit < 1 then
        raise exception 'invalid_quota_limit';
    end if;
    if coalesce(trim(p_user_id), '') = '' or coalesce(trim(p_operation), '') = '' then
        raise exception 'invalid_quota_input';
    end if;

    insert into public.jobcopilot_usage (user_id, day, used, operations)
    values (p_user_id, p_day, 0, '{}'::jsonb)
    on conflict (user_id, day) do nothing;

    select used, operations
      into current_used, current_operations
      from public.jobcopilot_usage
     where user_id = p_user_id and day = p_day
     for update;

    if current_used >= p_limit then
        raise exception 'quota_exceeded';
    end if;

    next_operations := jsonb_set(
        coalesce(current_operations, '{}'::jsonb),
        array[p_operation],
        to_jsonb(coalesce((current_operations ->> p_operation)::integer, 0) + 1),
        true
    );

    update public.jobcopilot_usage
       set used = current_used + 1,
           operations = next_operations,
           updated_at = now()
     where user_id = p_user_id and day = p_day;

    return jsonb_build_object(
        'day', p_day::text,
        'used', current_used + 1,
        'operations', next_operations
    );
end;
$$;

revoke all on function public.jobcopilot_consume_quota(text, date, text, integer)
    from public, anon, authenticated;
grant execute on function public.jobcopilot_consume_quota(text, date, text, integer)
    to service_role;
