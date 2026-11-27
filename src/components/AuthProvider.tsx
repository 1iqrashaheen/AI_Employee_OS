'use client';
import { createContext, useContext, useEffect, useState } from 'react';
import { clearSession, fetchMe, getSavedIdentity, initializeSession, type User, type Company } from '@/lib/api';
type AuthContextValue={user:User|null;company:Company|null;loading:boolean;setIdentity:(u:User|null,c:Company|null)=>void;signOut:()=>void};
const AuthContext=createContext<AuthContextValue>({user:null,company:null,loading:true,setIdentity:()=>{},signOut:()=>{}});
export function AuthProvider({children}:{children:React.ReactNode}) {
 const [user,setUser]=useState<User|null>(null); const [company,setCompany]=useState<Company|null>(null); const [loading,setLoading]=useState(true);
 const setIdentity=(u:User|null,c:Company|null)=>{setUser(u);setCompany(c);};
 const signOut=()=>{clearSession();setIdentity(null,null);window.location.href='/login';};
 useEffect(()=>{(async()=>{const saved=getSavedIdentity();setIdentity(saved.user,saved.company);const ok=await initializeSession();if(ok){try{const me=await fetchMe();setIdentity(me.user,me.company);}catch{setIdentity(null,null);}}else if(!saved.user){setIdentity(null,null);}setLoading(false);})();},[]);
 return <AuthContext.Provider value={{user,company,loading,setIdentity,signOut}}>{children}</AuthContext.Provider>;
}
export const useAuth=()=>useContext(AuthContext);
