'use client';
import { useEffect } from 'react';
import { useAuth } from './AuthProvider';
export default function Protected({children}:{children:React.ReactNode}) { const {user,loading}=useAuth(); useEffect(()=>{if(!loading&&!user)window.location.href='/login';},[loading,user]); if(loading||!user)return <div className="screen-loader"><div className="spinner"/><span>Preparing your workspace…</span></div>; return <>{children}</>; }
