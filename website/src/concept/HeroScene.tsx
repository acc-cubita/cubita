import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Float, RoundedBox, Environment, Lightformer } from '@react-three/drei'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'

/**
 * صحنه‌ی سه‌بعدیِ heroِ صفحه‌ی کانسپت — خوشه‌ای منتخب از المان‌های حسابداری، براق و
 * پریمیوم. بازتاب‌ها از یک «استودیوی مجازیِ محلی» می‌آید: چند Lightformer داخلِ
 * <Environment> که یک cube-map رنگی می‌سازند — بدونِ HDRI/CDN و هیچ درخواستِ شبکه‌ای.
 * همین بازتاب است که فلز (طلا، کارتِ بانکی، گاوصندوق) را حرفه‌ای و گران‌قیمت نشان می‌دهد.
 *
 * چیدمان: در دسکتاپ خوشه به چپ منتقل می‌شود تا متنِ سمتِ راست باز بماند؛ روی موبایل مرکز.
 * پرفورمنس: بدونِ سایه، dpr سقف‌دار، Environment فقط یک‌بار رندر می‌شود (frames=1)، کانواس lazy.
 */

const GOLD = '#f5c542'
const GOLD_HI = '#ffe89a'
const BLUE = '#4f7cff'
const TEAL = '#22d3ee'
const PAPER = '#eef3ff'
const DARK = '#141b2c'

function CoinStack({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  const coins = [0, 0.115, 0.23, 0.345]
  return (
    <Float speed={1.2} rotationIntensity={0.25} floatIntensity={0.6}>
      <group position={position} scale={scale} rotation={[0, 0.3, 0.06]}>
        {coins.map((y, i) => (
          <group key={i} position={[Math.sin(i * 1.7) * 0.03, y, Math.cos(i * 1.7) * 0.03]}>
            <mesh>
              <cylinderGeometry args={[0.42, 0.42, 0.105, 56]} />
              <meshPhysicalMaterial color={GOLD} metalness={1} roughness={0.2} clearcoat={0.5} clearcoatRoughness={0.25} envMapIntensity={1.4} emissive="#4a3400" emissiveIntensity={0.1} />
            </mesh>
            <mesh position={[0, 0.053, 0]} rotation={[Math.PI / 2, 0, 0]}>
              <torusGeometry args={[0.36, 0.018, 12, 48]} />
              <meshPhysicalMaterial color={GOLD_HI} metalness={1} roughness={0.28} envMapIntensity={1.2} />
            </mesh>
          </group>
        ))}
      </group>
    </Float>
  )
}

function BarChart({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  const heights = [0.5, 0.82, 0.66, 1.15, 0.92]
  return (
    <Float speed={1.4} rotationIntensity={0.3} floatIntensity={0.7}>
      <group position={position} scale={scale} rotation={[0.05, -0.5, 0]}>
        {heights.map((h, i) => (
          <RoundedBox key={i} args={[0.2, h, 0.2]} radius={0.045} smoothness={4} position={[i * 0.28 - 0.56, h / 2 - 0.2, 0]}>
            <meshPhysicalMaterial color={BLUE} metalness={0.4} roughness={0.28} clearcoat={0.7} clearcoatRoughness={0.25} envMapIntensity={1} emissive={BLUE} emissiveIntensity={0.35} />
          </RoundedBox>
        ))}
        {/* صفحه‌ی پایه‌ی شیشه‌ای */}
        <RoundedBox args={[1.6, 0.06, 0.5]} radius={0.03} smoothness={4} position={[0, -0.22, 0]}>
          <meshPhysicalMaterial color={DARK} metalness={0.3} roughness={0.15} transmission={0.35} thickness={0.4} clearcoat={1} envMapIntensity={1.4} />
        </RoundedBox>
      </group>
    </Float>
  )
}

function InvoiceCard({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  return (
    <Float speed={1.5} rotationIntensity={0.4} floatIntensity={0.9}>
      <group position={position} scale={scale} rotation={[0.12, 0.42, -0.1]}>
        <RoundedBox args={[1, 1.35, 0.05]} radius={0.07} smoothness={5}>
          <meshPhysicalMaterial color={PAPER} metalness={0.05} roughness={0.35} clearcoat={0.5} clearcoatRoughness={0.4} envMapIntensity={0.7} />
        </RoundedBox>
        {/* سربرگ */}
        <mesh position={[0, 0.5, 0.031]}>
          <boxGeometry args={[1, 0.3, 0.01]} />
          <meshStandardMaterial color={BLUE} emissive={BLUE} emissiveIntensity={0.45} />
        </mesh>
        {/* سطرها */}
        {[0.12, -0.02, -0.16, -0.3].map((y, i) => (
          <mesh key={i} position={[-0.12, y, 0.031]}>
            <boxGeometry args={[i % 2 ? 0.5 : 0.72, 0.05, 0.005]} />
            <meshStandardMaterial color="#c4cde0" />
          </mesh>
        ))}
        {/* بلوکِ جمعِ کل (تأکیدِ فیروزه‌ای) */}
        <mesh position={[0.22, -0.46, 0.031]}>
          <boxGeometry args={[0.42, 0.12, 0.008]} />
          <meshStandardMaterial color={TEAL} emissive={TEAL} emissiveIntensity={0.5} />
        </mesh>
      </group>
    </Float>
  )
}

function BankCard({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  return (
    <Float speed={1.3} rotationIntensity={0.5} floatIntensity={0.85}>
      <group position={position} scale={scale} rotation={[0.18, 0.55, 0.08]}>
        <RoundedBox args={[1.3, 0.82, 0.045]} radius={0.09} smoothness={5}>
          <meshPhysicalMaterial color="#26385c" metalness={0.95} roughness={0.13} clearcoat={1} clearcoatRoughness={0.12} envMapIntensity={2.3} />
        </RoundedBox>
        {/* تراشه‌ی طلایی */}
        <RoundedBox args={[0.22, 0.17, 0.02]} radius={0.03} smoothness={4} position={[-0.36, 0.14, 0.028]}>
          <meshPhysicalMaterial color={GOLD} metalness={1} roughness={0.25} clearcoat={0.6} envMapIntensity={1.4} />
        </RoundedBox>
        {/* نوارِ شماره */}
        <mesh position={[0.06, -0.22, 0.026]}>
          <boxGeometry args={[0.78, 0.07, 0.005]} />
          <meshStandardMaterial color={TEAL} emissive={TEAL} emissiveIntensity={0.4} metalness={0.6} roughness={0.4} />
        </mesh>
        {/* لوگوی گوشه */}
        <mesh position={[0.42, 0.22, 0.028]}>
          <circleGeometry args={[0.08, 32]} />
          <meshStandardMaterial color={GOLD_HI} metalness={0.9} roughness={0.3} />
        </mesh>
      </group>
    </Float>
  )
}

function Calculator({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  const btns: [number, number, number][] = []
  for (let r = 0; r < 4; r++) for (let c = 0; c < 3; c++) btns.push([c * 0.19 - 0.19, -0.05 - r * 0.185, 0.085])
  return (
    <Float speed={1.25} rotationIntensity={0.4} floatIntensity={0.7}>
      <group position={position} scale={scale} rotation={[0.12, -0.5, -0.08]}>
        <RoundedBox args={[0.78, 1.02, 0.15]} radius={0.07} smoothness={5}>
          <meshPhysicalMaterial color="#1a2338" metalness={0.65} roughness={0.22} clearcoat={0.9} clearcoatRoughness={0.22} envMapIntensity={1.7} />
        </RoundedBox>
        {/* نمایشگر */}
        <mesh position={[0, 0.34, 0.078]}>
          <boxGeometry args={[0.58, 0.22, 0.01]} />
          <meshStandardMaterial color="#04121a" emissive={TEAL} emissiveIntensity={0.85} />
        </mesh>
        {btns.map((p, i) => (
          <RoundedBox key={i} args={[0.14, 0.13, 0.035]} radius={0.03} smoothness={3} position={p}>
            <meshPhysicalMaterial color={i === 11 ? BLUE : '#28324c'} emissive={i === 11 ? BLUE : '#000'} emissiveIntensity={i === 11 ? 0.5 : 0} metalness={0.4} roughness={0.45} clearcoat={0.5} envMapIntensity={0.9} />
          </RoundedBox>
        ))}
      </group>
    </Float>
  )
}

function Safe({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  return (
    <Float speed={1.1} rotationIntensity={0.28} floatIntensity={0.55}>
      <group position={position} scale={scale} rotation={[0.16, 0.5, 0]}>
        <RoundedBox args={[1.05, 1.05, 0.7]} radius={0.08} smoothness={5}>
          <meshPhysicalMaterial color="#2a3958" metalness={0.85} roughness={0.2} clearcoat={0.8} clearcoatRoughness={0.2} envMapIntensity={1.9} />
        </RoundedBox>
        <RoundedBox args={[0.78, 0.82, 0.06]} radius={0.05} smoothness={4} position={[0, 0, 0.36]}>
          <meshPhysicalMaterial color="#35466a" metalness={0.9} roughness={0.16} clearcoat={0.9} envMapIntensity={2} />
        </RoundedBox>
        {/* چرخِ رمز */}
        <mesh position={[0.14, 0, 0.42]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.15, 0.045, 16, 40]} />
          <meshPhysicalMaterial color={GOLD} metalness={1} roughness={0.2} clearcoat={0.5} envMapIntensity={1.4} />
        </mesh>
        <mesh position={[0.14, 0, 0.43]}>
          <cylinderGeometry args={[0.05, 0.05, 0.1, 24]} />
          <meshPhysicalMaterial color={GOLD_HI} metalness={1} roughness={0.28} envMapIntensity={1.2} />
        </mesh>
      </group>
    </Float>
  )
}

function VirtualStudio() {
  // «استودیوی مجازی» — چند صفحه‌ی نوری که به‌صورتِ cube-map بازتاب می‌شوند. کاملاً محلی.
  return (
    <Environment resolution={320} frames={1}>
      <color attach="background" args={['#070b16']} />
      {/* سافت‌باکسِ اصلی — نوارِ نورِ براق روی فلزها */}
      <Lightformer intensity={3.4} position={[0, 2, 5.5]} scale={[11, 6, 1]} color="#ffffff" />
      <Lightformer intensity={2} position={[-3.5, 1, 5]} scale={[6, 7, 1]} color="#dfe8ff" />
      {/* رنگ‌مایه‌های صحنه که در فلز منعکس می‌شوند */}
      <Lightformer intensity={1.8} position={[-5, 1.5, 2]} scale={[4, 8, 1]} color={BLUE} />
      <Lightformer intensity={1.5} position={[5, -1, 2]} scale={[5, 6, 1]} color={GOLD} />
      <Lightformer intensity={1.1} position={[0, -4, 3]} scale={[9, 3, 1]} color={TEAL} />
      <Lightformer intensity={1} form="ring" position={[3, 3, -3]} scale={3.5} color="#ffffff" />
    </Environment>
  )
}

function Cluster({ scrollRef, reduced }: { scrollRef: React.MutableRefObject<number>; reduced: boolean }) {
  const group = useRef<THREE.Group>(null!)
  const auto = useRef(0)
  const { size, viewport } = useThree()
  useFrame((state, delta) => {
    const g = group.current
    if (!g) return
    auto.current += delta * (reduced ? 0 : 0.1)
    const s = scrollRef.current
    // انتقال به چپ در دسکتاپ تا متنِ سمتِ راست باز بماند
    const targetX = size.width > 860 ? -viewport.width * 0.2 : 0
    g.position.x = THREE.MathUtils.lerp(g.position.x, targetX, 0.1)
    g.rotation.y = auto.current + s * Math.PI * 0.7
    g.rotation.x = THREE.MathUtils.lerp(g.rotation.x, state.pointer.y * -0.18 + s * 0.28, 0.06)
    g.position.y = THREE.MathUtils.lerp(g.position.y, -s * 1.5, 0.08)
  })
  return (
    <group ref={group}>
      <CoinStack position={[-1.7, -1.1, 0.3]} scale={0.9} />
      <BankCard position={[0.2, 0.35, 0.9]} scale={0.92} />
      <InvoiceCard position={[-1.35, 1.15, 0.2]} scale={0.82} />
      <BarChart position={[1.65, -0.85, -0.1]} scale={0.88} />
      <Calculator position={[1.45, 1.1, 0.25]} scale={0.85} />
      <Safe position={[0.15, -1.7, -0.5]} scale={0.8} />
    </group>
  )
}

export default function HeroScene() {
  const scrollRef = useRef(0)
  const reduced = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

  useEffect(() => {
    const onScroll = () => {
      const p = Math.min(1, Math.max(0, window.scrollY / (window.innerHeight || 800)))
      scrollRef.current = p
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <Canvas
      camera={{ position: [0, 0, 8.2], fov: 42 }}
      dpr={[1, 1.8]}
      gl={{ antialias: true, alpha: true }}
      style={{ width: '100%', height: '100%' }}
    >
      <ambientLight intensity={0.35} />
      <directionalLight position={[4, 5, 6]} intensity={1.6} color="#fff6e6" />
      <pointLight position={[-6, 2, 3]} intensity={45} color={BLUE} distance={22} />
      <pointLight position={[6, -3, 2]} intensity={35} color={GOLD} distance={22} />
      <VirtualStudio />
      <Cluster scrollRef={scrollRef} reduced={reduced} />
    </Canvas>
  )
}
